"""Live provider + real authenticated application storage smoke check."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from ugly_services.settings import Settings
from ugly_services.backend import Backend
from ugly_services.chat import reply
from ugly_services.revision import revision

settings=Settings.read()
backend=Backend(settings)
conversations_before=[]
try:
    backend.signin(os.environ["TEST_EMAIL"],os.environ["TEST_PASSWORD"])
    previous=backend.rpc("orders")
    conversation=backend.rpc("new_conversation")["id"]
    reply(backend,settings,conversation,"Hello. What is the price of Pizza? This is a synthetic integration check.")
    messages=backend.rpc("messages",{"conversation":conversation})
    assert len(messages)==2
    assistant=messages[-1]["content"]
    assert "unavailable" not in assistant.lower(),"The provider returned a fallback instead of a live reply."
    assert len(assistant.strip())>0
    assert settings.groq_key not in assistant
    assert "200" in assistant,"The answer did not retain the fixed menu price."
    assert len(backend.rpc("orders"))==len(previous),"Chat must not create an order."
    for path in Path(".").rglob("*.py"):
        if "data" not in path.parts and "__pycache__" not in path.parts:
            assert settings.groq_key not in path.read_text(encoding="utf-8-sig")
    proof={"passed":True,"scope":"native-receptionist-live-groq-integration",
        "sourceHash":revision(),"generatedAt":datetime.now(timezone.utc).isoformat(),
        "model":settings.groq_model,"checks":["Actual Groq SDK returned a non-fallback reply",
        "Menu price retained","Authenticated conversation persisted","Chat did not create an order",
        "Configured key absent from Python source and reply"],"dataSent":"Synthetic test text only"}
    Path("evidence/groq-app-integration.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    print("PASS: real receptionist AI reply persisted; menu price retained; no order created by chat.")
finally:
    if backend.session:
        backend.signout()
    backend.close()

