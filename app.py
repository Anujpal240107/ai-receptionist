import streamlit as st
from groq import Groq
import os

# Page setup
st.set_page_config(page_title="AI Restaurant Receptionist", page_icon="🍕")
st.title("🍕 AI Restaurant Receptionist")
st.caption("Order food like you're talking to a real receptionist. Type 'reset' to clear conversation.")

# Get API key from Streamlit secrets
import streamlit as st
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

system_prompt = """You are a restaurant receptionist. Take the customer's name, show the menu (Pizza ₹200, Burger ₹150, Pasta ₹180, Cold Drink ₹50), take their order, ask for delivery address, confirm the order and total price, then end politely. Always respond in English only. Before confirming the order, ask the customer if they will pay by Cash on Delivery or Online Payment. Always repeat the customer's full delivery address when confirming the order. Never write [Your Address]. Keep replies under 80 words. Do not repeat the full menu after the order is taken. If the customer has already provided their delivery address, do not ask for it again. Use that exact address when confirming the order. Never ask for address details after the address is already given. After the customer provides their delivery address, ask for their phone number. When confirming the order, repeat the phone number. If the phone number has already been given, do not ask again."""

# Initialize chat history
if "history" not in st.session_state:
    st.session_state.history = [{"role": "system", "content": system_prompt}]
    st.session_state.messages = []

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle user input
if prompt := st.chat_input("Type your message here..."):
    # Add user message to display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Reset logic
    if prompt.lower() == "reset":
        st.session_state.history = [{"role": "system", "content": system_prompt}]
        assistant_reply = "Conversation reset. How can I help you?"
    else:
        # Call Groq
        st.session_state.history.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="allam-2-7b",
            messages=st.session_state.history,
            max_tokens=300
        )
        assistant_reply = response.choices[0].message.content
        st.session_state.history.append({"role": "assistant", "content": assistant_reply})

    # Display assistant reply
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    with st.chat_message("assistant"):
        st.markdown(assistant_reply)
