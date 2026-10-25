"""Supabase Auth and authenticated, RLS-protected application RPCs.

Tokens stay in this Streamlit server's per-session state. No service-role bypass.
"""
import time
import httpx
from .monitoring import alert

class ServiceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

# Do not reflect remote SQL details, HTTP bodies, credentials or customer data.
_MESSAGES = {
    "22023": "Check the supplied details and try again.",
    "23502": "Complete all required details.",
    "23503": "The selected conversation or item is unavailable.",
    "23514": "Some details are outside their allowed limits.",
    "22P02": "The supplied identifier or file is invalid.",
    "42501": "You do not have access to this item or action.",
    "28000": "Your session ended. Sign in again.",
}
_QUOTA_MESSAGES = {"Usage allowance reached", "Private file allowance reached",
                  "Start a new conversation", "Delete an old conversation first",
                  "A reply is still in progress", "Reply is no longer current"}

class Backend:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.http = httpx.Client(timeout=httpx.Timeout(20, connect=10),
                                 follow_redirects=False, transport=transport or
                                 httpx.HTTPTransport(local_address="0.0.0.0", retries=1))
        self.session = None

    def _request(self, path, payload=None, token=None, method="POST"):
        headers = {"apikey": self.settings.publishable_key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            r = self.http.request(method, self.settings.supabase_url + path,
                                  headers=headers, json=payload)
            data = {} if r.is_success and not r.content else r.json()
        except (httpx.HTTPError, ValueError):
            alert("backend_failed")
            raise ServiceError("The service is unavailable. No successful save was confirmed.", 503) from None
        if not r.is_success:
            code = str(data.get("code", "")) if isinstance(data, dict) else ""
            message = str(data.get("message", "")) if isinstance(data, dict) else ""
            if code in _MESSAGES:
                raise ServiceError(_MESSAGES[code], 401 if code == "28000" else r.status_code)
            if code == "P0001" and message in _QUOTA_MESSAGES:
                raise ServiceError(message + ".", 429)
            if r.status_code == 429:
                raise ServiceError("Too many attempts. Wait before trying again.", 429)
            if path.startswith("/auth/"):
                raise ServiceError("Account request failed. Check your credentials and email confirmation.", r.status_code)
            raise ServiceError("The request was rejected. Nothing was confirmed.", r.status_code)
        return data

    def signin(self, email, password):
        data = self._request("/auth/v1/token?grant_type=password",
                             {"email": email.strip(), "password": password})
        self._set_session(data)
        return data["user"]

    def signup(self, email, password):
        if len(password) < 12 or len(password) > 128:
            raise ServiceError("Choose a password with 12 to 128 characters.")
        data = self._request("/auth/v1/signup", {"email": email.strip(), "password": password})
        if data.get("access_token"):
            self._set_session(data)
        return bool(self.session)

    def _set_session(self, data):
        if not data.get("access_token") or not data.get("refresh_token"):
            raise ServiceError("The identity service did not establish a session.", 401)
        self.session = {k: data[k] for k in ("access_token", "refresh_token", "user")}
        self.session["expires_at"] = time.time() + data.get("expires_in", 3600)

    def token(self):
        if not self.session:
            raise ServiceError("Sign in to continue.", 401)
        if self.session["expires_at"] < time.time() + 30:
            try:
                data = self._request("/auth/v1/token?grant_type=refresh_token",
                                     {"refresh_token": self.session["refresh_token"]})
                self._set_session(data)
            except ServiceError:
                self.session = None
                raise
        return self.session["access_token"]

    def signout(self):
        token = self.token()
        self._request("/auth/v1/logout?scope=local", {}, token)
        self.session = None

    def rpc(self, action, payload=None):
        try:
            return self._request("/rest/v1/rpc/reception_service",
                                 {"action": action, "payload": payload or {}}, self.token())
        except ServiceError as e:
            if e.status == 401:
                self.session = None
            raise

    def close(self):
        self.http.close()

