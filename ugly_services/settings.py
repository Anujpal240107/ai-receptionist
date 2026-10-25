"""Only server-side settings. No privileged database key is needed by this app."""
import os
import re
import base64
import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

class ConfigurationError(Exception):
    pass

@dataclass(frozen=True)
class Settings:
    supabase_url: str
    publishable_key: str
    project: str
    environment: str
    groq_key: str = field(default="", repr=False)
    groq_model: str = ""
    sentry_dsn: str = field(default="", repr=False)
    origin: str = ""

    @classmethod
    def read(cls, values=None):
        v = os.environ if values is None else values
        url = v.get("SUPABASE_URL", "").rstrip("/")
        project = v.get("EXPECTED_SUPABASE_PROJECT", "")
        parts = urlsplit(url)
        if (not re.fullmatch(r"[a-z0-9]{20}", project) or
            parts.scheme != "https" or parts.hostname != project + ".supabase.co" or
            parts.username or parts.password or parts.port or parts.query or parts.fragment or parts.path):
            raise ConfigurationError("The Supabase project binding is missing or invalid.")
        key = v.get("SUPABASE_PUBLISHABLE_KEY", "")
        valid_key = key.startswith("sb_publishable_")
        if key.startswith("eyJ"):
            try:
                claims = json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "==="))
                valid_key = claims.get("role") == "anon"
            except (ValueError, IndexError):
                valid_key = False
        if not valid_key:
            raise ConfigurationError("Use the Supabase publishable key, never a server secret.")
        environment = v.get("RECEPTION_ENV", "development")
        if environment not in ("development", "production", "test"):
            raise ConfigurationError("RECEPTION_ENV must be development, production or test.")
        origin = v.get("RECEPTION_ORIGIN", "")
        if environment == "production":
            p = urlsplit(origin)
            if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment:
                raise ConfigurationError("Production requires the actual HTTPS receptionist origin.")
        return cls(url, key, project, environment, v.get("GROQ_API_KEY", ""),
                   v.get("GROQ_MODEL", ""), v.get("SENTRY_DSN", ""), origin)

