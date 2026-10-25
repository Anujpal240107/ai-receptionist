"""The runtime fingerprint excludes credentials, test data and mutable evidence."""
import hashlib
from pathlib import Path

RUNTIME_FILES = (
    "app.py", "requirements.txt", ".streamlit/config.toml", "ugly-saas-adapter.json",
    "migrations/001_receptionist.sql", "ugly_services/__init__.py", "ugly_services/settings.py",
    "ugly_services/backend.py", "ugly_services/chat.py", "ugly_services/monitoring.py",
    "ugly_services/revision.py",
)

def revision():
    root=Path(__file__).resolve().parents[1]
    h=hashlib.sha256()
    for name in RUNTIME_FILES:
        h.update(name.encode())
        h.update((root/name).read_text(encoding="utf-8-sig").replace("\r\n","\n").encode())
    return h.hexdigest()

