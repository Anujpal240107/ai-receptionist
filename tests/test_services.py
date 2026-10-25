import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from ugly_services.settings import Settings, ConfigurationError
from ugly_services.backend import Backend, ServiceError
from ugly_services.chat import reply
from ugly_services.monitoring import sanitize

PROJECT = "a" * 20
def settings(**kw):
    return Settings("https://" + PROJECT + ".supabase.co", "sb_publishable_test", PROJECT, "test", **kw)
def response(request, body, status=200):
    return httpx.Response(status, json=body, request=request)

class Services(unittest.TestCase):
    def test_environment_rejects_wrong_project_and_non_tls(self):
        base={"SUPABASE_URL":"https://"+PROJECT+".supabase.co","EXPECTED_SUPABASE_PROJECT":PROJECT,"SUPABASE_PUBLISHABLE_KEY":"sb_publishable_test"}
        Settings.read(base)
        for value in ("http://"+PROJECT+".supabase.co", "https://elsewhere.test", "https://user:pass@"+PROJECT+".supabase.co", "https://"+PROJECT+".supabase.co/?key=leak"):
            with self.assertRaises(ConfigurationError):Settings.read({**base,"SUPABASE_URL":value})

    def test_server_key_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            Settings.read({"SUPABASE_URL":"https://"+PROJECT+".supabase.co","EXPECTED_SUPABASE_PROJECT":PROJECT,"SUPABASE_PUBLISHABLE_KEY":"sb_secret_unsafe"})

    def test_production_needs_https(self):
        with self.assertRaises(ConfigurationError):
            Settings.read({"SUPABASE_URL":"https://"+PROJECT+".supabase.co","EXPECTED_SUPABASE_PROJECT":PROJECT,"SUPABASE_PUBLISHABLE_KEY":"sb_publishable_test","RECEPTION_ENV":"production","RECEPTION_ORIGIN":"http://localhost"})

    def test_no_session_no_request(self):
        with self.assertRaises(ServiceError):
            Backend(settings()).rpc("orders")

    def test_auth_and_expired_session_refresh(self):
        calls=[]
        def handler(r):
            calls.append(r)
            return response(r,{"access_token":"access","refresh_token":"refresh","expires_in":3600,"user":{"id":"test"}})
        b=Backend(settings(),httpx.MockTransport(handler))
        b.signin(" test@example.test ","private-password")
        b.session["expires_at"]=0
        self.assertEqual(b.token(),"access")
        self.assertEqual(len(calls),2)
        self.assertIn("refresh_token",str(calls[1].url))

    def test_refresh_failure_clears_session(self):
        b=Backend(settings(),httpx.MockTransport(lambda r:response(r,{},401)))
        b.session={"expires_at":0,"refresh_token":"private","access_token":"old"}
        with self.assertRaises(ServiceError):b.token()
        self.assertIsNone(b.session)

    def test_logout_is_remote_before_local_clear(self):
        calls=[]
        b=Backend(settings(),httpx.MockTransport(lambda r:(calls.append(r),httpx.Response(204,request=r))[1]))
        b.session={"expires_at":time.time()+100,"refresh_token":"private","access_token":"access"}
        b.signout()
        self.assertIsNone(b.session)
        self.assertEqual(calls[0].headers["Authorization"],"Bearer access")
        self.assertEqual(calls[0].url.path,"/auth/v1/logout")

    def test_remote_error_does_not_expose_payload(self):
        b=Backend(settings(),httpx.MockTransport(lambda r:response(r,{"message":"password=private@example.test key=SECRET","details":"private"},500)))
        b.session={"expires_at":time.time()+100,"access_token":"access"}
        with self.assertRaises(ServiceError) as caught:b.rpc("orders")
        self.assertNotIn("private",str(caught.exception))
        self.assertNotIn("SECRET",str(caught.exception))

    def test_quota_rejection_is_clear(self):
        b=Backend(settings(),httpx.MockTransport(lambda r:response(r,{"code":"P0001","message":"Usage allowance reached"},400)))
        b.session={"expires_at":time.time()+100,"access_token":"access"}
        with self.assertRaises(ServiceError) as caught:b.rpc("chat_start")
        self.assertEqual(caught.exception.status,429)

    def test_network_outage_fails_closed(self):
        def handler(r):raise httpx.ConnectError("secret error",request=r)
        b=Backend(settings(),httpx.MockTransport(handler))
        b.session={"expires_at":time.time()+100,"access_token":"access"}
        with self.assertRaises(ServiceError) as caught:b.rpc("place_order")
        self.assertEqual(caught.exception.status,503)

    def test_monitoring_drops_pii_and_credentials(self):
        event={"event_id":"a"*32,"message":"PRIVATE","request":{"headers":{"Authorization":"SECRET"}},"user":{"email":"private@example.test"},"extra":{"order":"PRIVATE"},"tags":{"category":"provider_failed","email":"PRIVATE"}}
        clean=sanitize(event)
        self.assertNotIn("PRIVATE",json.dumps(clean))
        self.assertNotIn("SECRET",json.dumps(clean))
        self.assertEqual(clean["tags"],{"service":"ai-receptionist","category":"provider_failed"})
        self.assertIsNone(sanitize({"tags":{"category":"unknown"}}))

    def test_missing_groq_does_not_claim_ai_success(self):
        backend=SimpleNamespace(rpc=lambda *_:self.fail("Should not reserve a provider request"))
        with self.assertRaises(ServiceError):reply(backend,settings(),"id","hello")

    def test_provider_failure_saves_safe_reply_and_never_places_order(self):
        actions=[]
        class FakeBackend:
            def rpc(self,action,payload=None):
                actions.append((action,payload))
                if action=="chat_start":return {"request_id":"r","messages":[{"role":"user","content":"hello"}]}
        def failed_factory(**kw):raise RuntimeError("API_KEY=SECRET private order")
        with patch("ugly_services.chat.alert"):
            reply(FakeBackend(),settings(groq_key="SECRET",groq_model="model"),"conv","hello",failed_factory)
        self.assertEqual([a for a,_ in actions],["chat_start","provider_failure","chat_finish"])
        self.assertNotIn("SECRET",str(actions))
        self.assertIn("No order",actions[-1][1]["content"])

    def test_provider_uses_bounded_context_and_tokens(self):
        seen={}
        class FakeClient:
            def __init__(self,**kw):seen.update(kw);self.chat=SimpleNamespace(completions=self)
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def create(self,**kw):
                seen.update(kw)
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Hello"))])
        class FakeBackend:
            def rpc(self,action,payload=None):
                if action=="chat_start":return {"request_id":"r","messages":[{"role":"user","content":"hello"}]}
        reply(FakeBackend(),settings(groq_key="SECRET",groq_model="model"),"conv","hello",FakeClient)
        self.assertEqual(seen["max_tokens"],300)
        self.assertEqual(seen["max_retries"],0)
        self.assertEqual(seen["timeout"],20)

if __name__=="__main__":unittest.main()

