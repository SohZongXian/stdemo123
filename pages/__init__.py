from .chatbot import show_page2
from .dashboard import show_page1
import streamlit as st

def show_main():
    user_name = st.session_state.get("user_name", "User")
    st.markdown(f"<h1 style='text-align: center; color: #FFFFFF;'>Welcome {user_name}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 18px; line-height: 1.5;'>Use the navigation bar above to explore the app's features.</p>", unsafe_allow_html=True)