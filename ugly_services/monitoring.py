"""Whitelisted Sentry alerts; no automatic request/session/customer instrumentation."""
import logging
import sentry_sdk

ALLOWED = {"provider_failed", "backend_failed", "verification_probe"}

def sanitize(event, hint=None):
    category = event.get("tags", {}).get("category")
    if category not in ALLOWED:
        return None
    return {"event_id": event.get("event_id"), "timestamp": event.get("timestamp"),
            "platform": "python", "level": "error", "message": "Receptionist service failure",
            "tags": {"service": "ai-receptionist", "category": category}}

def configure(settings):
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, default_integrations=False,
                        auto_enabling_integrations=False, send_default_pii=False,
                        traces_sample_rate=0, environment=settings.environment,
                        before_send=sanitize)

def alert(category):
    if category not in ALLOWED:
        raise ValueError("Unknown event category")
    logging.getLogger("receptionist.audit").warning("service_event:%s", category)
    return sentry_sdk.capture_event({"message": "Receptionist service failure",
                                     "level": "error", "tags": {"category": category}})

