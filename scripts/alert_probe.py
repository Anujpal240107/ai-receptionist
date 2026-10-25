"""Send one synthetic, sanitized native-app error to the configured Sentry endpoint."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sentry_sdk
from sentry_sdk.transport import HttpTransport
from ugly_services.settings import Settings
from ugly_services.monitoring import sanitize

receipts=[]
sent=[]
class ReceiptTransport(HttpTransport):
    def _send_envelope(self,envelope):
        for item in envelope.items:
            if item.headers.get("type")=="event":
                payload=item.payload.json
                assert payload.get("request") is None
                assert payload.get("user") is None
                assert "PRIVATE_SENTINEL" not in json.dumps(payload)
                sent.append(payload.get("event_id"))
        return super()._send_envelope(envelope)

    def _request(self,*args,**kwargs):
        response=super()._request(*args,**kwargs)
        receipts.append(response.status)
        return response

settings=Settings.read()
assert settings.sentry_dsn,"The app has no monitoring destination."
sentry_sdk.init(dsn=settings.sentry_dsn,default_integrations=False,
                auto_enabling_integrations=False,send_default_pii=False,
                transport=ReceiptTransport,before_send=sanitize,
                send_client_reports=False,traces_sample_rate=0)
event_id=sentry_sdk.capture_event({"message":"PRIVATE_SENTINEL",
    "user":{"email":"PRIVATE_SENTINEL@example.test"},"request":{"body":"PRIVATE_SENTINEL"},
    "tags":{"category":"verification_probe"}})
sentry_sdk.flush(20)
assert sent==[event_id],"No sanitized native event was sent."
assert any(200<=status<300 for status in receipts),"Sentry did not accept the alert."
Path("evidence").mkdir(exist_ok=True)
Path("evidence/alert-delivery.json").write_text(json.dumps({
    "passed":True,"scope":"native-receptionist-sentry-delivery",
    "generatedAt":datetime.now(timezone.utc).isoformat(),"eventId":event_id,
    "httpStatus":receipts[0],"customerDataRemoved":True},indent=2),encoding="utf-8")
print("PASS: Sentry accepted the sanitized native receptionist alert.")

