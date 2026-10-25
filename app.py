"""Original Streamlit/Groq receptionist, integrated with Ugly SaaS foundations."""
import base64
import html
import json
import os
import uuid
import streamlit as st
from ugly_services.settings import Settings, ConfigurationError
from ugly_services.backend import Backend, ServiceError
from ugly_services.chat import reply
from ugly_services.monitoring import configure, alert

st.set_page_config(page_title="AI Restaurant Receptionist", page_icon="🍕", layout="centered")
st.title("🍕 AI Restaurant Receptionist")
st.caption("A little ugly. Real saved orders. Powered by Ugly SaaS.")

def private_download(label, raw, filename):
    """Bytes go only through the authorized WebSocket; no public Streamlit media URL."""
    encoded = base64.b64encode(raw).decode("ascii")
    st.iframe('<a download="' + html.escape(filename, quote=True) +
                    '" href="data:application/octet-stream;base64,' + encoded +
                    '" style="font:16px sans-serif;color:#006c4e">' +
                    html.escape(label) + '</a>', height=44)

def get_settings():
    values = dict(os.environ)
    try:
        for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "EXPECTED_SUPABASE_PROJECT",
                    "RECEPTION_ENV", "RECEPTION_ORIGIN", "GROQ_API_KEY", "GROQ_MODEL", "SENTRY_DSN"):
            if key in st.secrets:
                values[key] = str(st.secrets[key])
    except FileNotFoundError:
        pass
    return Settings.read(values)

def main():
    try:
        settings = get_settings()
    except ConfigurationError as e:
        st.error(str(e))
        st.info("The owner must connect the Ugly SaaS environment before this app can accept orders.")
        return
    if "_backend" not in st.session_state:
        st.session_state["_backend"] = Backend(settings)
        configure(settings)
    backend = st.session_state["_backend"]

    if not backend.session:
        st.subheader("Your own place at the table")
        st.write("Sign in with your Ugly SaaS account. Your conversations and orders stay in your account.")
        mode = st.radio("Account", ("Sign in", "Create account"), horizontal=True)
        with st.form("account", clear_on_submit=True):
            email = st.text_input("Email", max_chars=254)
            password = st.text_input("Password", type="password", max_chars=128)
            submit = st.form_submit_button(mode)
        if submit:
            if mode == "Sign in":
                backend.signin(email, password)
                st.rerun()
            else:
                active = backend.signup(email, password)
                if active:
                    st.rerun()
                st.success("Check your inbox for the Ugly SaaS confirmation email, then sign in here.")
        st.caption("Credentials are handled by Supabase Auth. No database password is needed here.")
        return

    profile = backend.rpc("bootstrap")
    with st.sidebar:
        st.write("Signed in")
        st.caption(backend.session["user"].get("email", ""))
        if st.button("Sign out"):
            backend.signout()
            st.session_state.clear()
            st.rerun()
        st.caption("Chats, orders and attachments expire after 90 days. Security events: 30 days.")
        st.caption("No payment is collected. An online preference is recorded as unpaid.")
    conversations = backend.rpc("conversations")
    if not conversations:
        st.info("Start a conversation to order or ask the receptionist.")
        if st.button("Start your first conversation"):
            backend.rpc("new_conversation")
            st.rerun()
        return

    choices = [c["id"] for c in conversations]
    selected = st.session_state.get("_conversation", choices[0])
    conversation = st.selectbox("Conversation", choices,
                                index=choices.index(selected) if selected in choices else 0,
                                format_func=lambda value: "Conversation " + value[:8])
    st.session_state["_conversation"] = conversation
    if st.button("New conversation"):
        new = backend.rpc("new_conversation")
        st.session_state["_conversation"] = new["id"]
        st.rerun()
    labels = ["Receptionist", "Order", "My orders", "My data"]
    if profile["operator"]:
        labels.append("Restaurant desk")
    tabs = st.tabs(labels)

    with tabs[0]:
        st.caption("AI chat is assistance. Only a saved order receipt confirms placement.")
        consent = st.checkbox("Allow my chat messages to be sent to Groq for AI replies.")
        if not settings.groq_key or not settings.groq_model:
            st.info("The owner has not connected Groq yet. The Order tab works independently.")
        for message in backend.rpc("messages", {"conversation": conversation}):
            with st.chat_message(message["role"]):
                st.write(message["content"])
        with st.form("chat", clear_on_submit=True):
            prompt = st.text_input("Message", max_chars=2000,
                                   placeholder="Ask about the menu, or type reset")
            sent = st.form_submit_button("Send", disabled=not consent or not settings.groq_key or not settings.groq_model)
        if sent:
            reply(backend, settings, conversation, prompt)
            st.rerun()
        if st.button("Clear this conversation"):
            backend.rpc("reset", {"conversation": conversation})
            st.rerun()

    with tabs[1]:
        st.subheader("Review it. Confirm it once.")
        st.caption("Menu prices are INR. The database calculates the authoritative total.")
        with st.form("order"):
            name = st.text_input("Customer name", max_chars=120)
            phone = st.text_input("Phone number", max_chars=25)
            address = st.text_area("Full delivery address", max_chars=600)
            payment = st.selectbox("Payment preference", ["Cash on Delivery", "Online Payment"])
            items = []
            for m in profile["menu"]:
                quantity = st.number_input(f'{m["name"]} · ₹{m["price"]}', min_value=0, max_value=20, step=1, key="quantity-" + m["sku"])
                if quantity:
                    items.append({"sku": m["sku"], "quantity": quantity})
            reviewed = st.form_submit_button("Review order")
        if reviewed:
            st.session_state["_draft"] = {
                "request_id": str(uuid.uuid4()), "conversation": conversation,
                "customer_name": name, "phone": phone, "address": address,
                "payment_preference": payment, "items": items}
        draft = st.session_state.get("_draft")
        if draft and draft["conversation"] == conversation:
            with st.container(border=True):
                st.write(draft["customer_name"])
                st.write(draft["address"])
                st.write(draft["phone"])
                st.write(draft["payment_preference"] + " · unpaid")
                prices = {m["sku"]: m for m in profile["menu"]}
                estimate = sum(prices[i["sku"]]["price"] * i["quantity"] for i in draft["items"])
                for i in draft["items"]:
                    st.write(f'{prices[i["sku"]]["name"]} × {i["quantity"]}')
                st.write(f"Total: ₹{estimate}")
                if st.button("Confirm and save order", type="primary"):
                    order = backend.rpc("place_order", draft)
                    st.session_state.pop("_draft", None)
                    st.session_state["_receipt"] = order
                    st.rerun()
        receipt = st.session_state.get("_receipt")
        if receipt:
            st.success(f'Order saved: {receipt["id"]} · ₹{receipt["total"]} · {receipt["status"]}')
            st.write("Delivery: " + receipt["address"] + " · " + receipt["phone"])
            st.caption("Payment remains unpaid. Restaurant fulfillment is handled at the Restaurant desk.")

    with tabs[2]:
        orders = backend.rpc("orders")
        for order in orders:
            with st.expander(f'{order["id"][:8]} · ₹{order["total"]} · {order["status"]}'):
                st.write(order["address"])
                st.write(order["phone"])
                st.write(order["payment_preference"] + " · " + order["payment_status"])
                for i in order["items"]:
                    st.write(f'{i["sku"]} × {i["quantity"]} · ₹{i["unit_price"]} each')
                private_download("Download receipt", json.dumps(order, ensure_ascii=False, indent=2).encode(),
                                 "receipt-" + order["id"] + ".json")
                st.caption("Private attachments: 256 KB each, 10 per order, 5 MB per account. Downloads are attachments; files are never executed or rendered.")
                with st.form("file-" + order["id"], clear_on_submit=True):
                    upload = st.file_uploader("Order attachment", type=["txt", "pdf", "png", "jpg", "jpeg"], key="upload-" + order["id"])
                    add = st.form_submit_button("Save private attachment")
                if add and upload is not None:
                    raw = upload.getvalue()
                    if not 1 <= len(raw) <= 262144:
                        raise ServiceError("Choose a file between 1 byte and 256 KB.")
                    backend.rpc("add_file", {"order_id": order["id"], "name": upload.name,
                                            "media_type": upload.type, "base64": base64.b64encode(raw).decode()})
                    st.rerun()
                for f in backend.rpc("files", {"order_id": order["id"]}):
                    st.write(f'{f["name"]} · {f["bytes"]} bytes')
                    if st.button("Prepare download", key="read-" + f["id"]):
                        data = backend.rpc("download_file", {"file_id": f["id"]})
                        st.session_state["_file"] = {"id": f["id"], **data}
                    prepared = st.session_state.get("_file")
                    if prepared and prepared["id"] == f["id"]:
                        private_download("Download private file", base64.b64decode(prepared["base64"]), prepared["name"])
                    if st.button("Delete attachment", key="delete-" + f["id"]):
                        backend.rpc("delete_file", {"file_id": f["id"]})
                        st.session_state.pop("_file", None)
                        st.rerun()
        if not orders:
            st.info("No saved orders yet.")

    with tabs[3]:
        st.write("Export or delete the receptionist data in your account.")
        st.caption("Clearing chat does not delete an order. Full deletion removes conversations, orders, items and attachment bytes. Your Ugly SaaS login remains.")
        if st.button("Prepare my export"):
            st.session_state["_export"] = backend.rpc("export")
        if "_export" in st.session_state:
            private_download("Download my data", json.dumps(st.session_state["_export"], ensure_ascii=False).encode(), "receptionist-data.json")
        confirm = st.checkbox("Delete my conversations, orders and private attachments permanently from active storage")
        if st.button("Delete my receptionist data", disabled=not confirm):
            backend.rpc("delete_data", {"confirm": "DELETE MY RECEPTIONIST DATA"})
            for key in ("_export", "_file", "_receipt", "_draft", "_conversation"):
                st.session_state.pop(key, None)
            st.success("Your active receptionist data was deleted.")
            st.rerun()
        st.caption("Encrypted recovery backups use the Ugly SaaS backup policy: 7-day retention with at least 3 verified copies. Copies can remain longer when maintenance is offline. A restored database must reapply deletions before reopening service.")

    if profile["operator"]:
        with tabs[4]:
            st.subheader("Restaurant desk")
            for order in backend.rpc("operator_orders"):
                with st.expander(f'{order["id"][:8]} · {order["status"]}'):
                    st.write(order["customer_name"])
                    st.write(order["address"])
                    st.write(order["phone"])
                    st.write(f'₹{order["total"]} · unpaid')
                    st.write(", ".join(f'{i["sku"]} × {i["quantity"]}' for i in order["items"]))
                    transitions = {"placed": ["accepted", "cancelled"], "accepted": ["completed", "cancelled"]}
                    if order["status"] in transitions:
                        status = st.selectbox("Next status", transitions[order["status"]], key="status-" + order["id"])
                        if st.button("Update order", key="update-" + order["id"]):
                            backend.rpc("order_status", {"order_id": order["id"], "status": status})
                            st.rerun()

try:
    main()
except ServiceError as error:
    st.error(str(error))
    if error.status == 401 and st.button("Return to sign in"):
        st.session_state.clear()
        st.rerun()
except Exception:
    alert("backend_failed")
    st.error("The receptionist is temporarily unavailable. No successful save was confirmed.")

