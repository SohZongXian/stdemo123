import os
import streamlit as st
from streamlit_navigation_bar import st_navbar
import msal
import pages as pg
from dotenv import load_dotenv
# Set page config to collapse sidebar by default
load_dotenv()
st.set_page_config(initial_sidebar_state="collapsed")

# Apply dark mode styling and adjust navbar positioning
st.markdown("""
    <style>
    body {
        background-color: #1E1E1E;  /* Dark mode background */
        color: #E0E0E0;           /* Light text for dark mode */
    }
    .main {
        background-color: #2A2A2A;  /* Slightly lighter dark for content area */
        padding: 20px;
        border-radius: 10px;
    }
    /* Ensure navbar is visible, positioned lower, and clickable */
    div[data-testid="stNavbar"] {
        background-color: #333;  /* Dark gray background */
        padding: 15px 0;        /* Increase vertical padding for height */
        margin-top: 50px;       /* Shift navbar further down from top */
        z-index: 1000;          /* Ensure it stays above other elements */
    }
    div[data-testid="stNavbar"] span {
        color: white !important;  /* Force white text for navbar items */
        font-size: 18px;          /* Text size for visibility */
        padding: 15px 30px;       /* Larger padding for bigger clickable area */
        display: inline-block;    /* Ensure span behaves as a clickable block */
        cursor: pointer;          /* Indicate clickability */
    }
    div[data-testid="stNavbar"] div {
        color: white !important;  /* Ensure all text elements are white */
    }
    .stTextInput > div > div > input {
        border: 2px solid #4a90e2;
        border-radius: 8px;
        padding: 10px;
        font-size: 16px;
        background-color: #333;  /* Dark input background */
        color: #E0E0E0;          /* Light text in input */
    }
    .stButton > button {
        background-color: #4a90e2;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #357abd;
    }
    .answer-box {
        background-color: #333;     /* Darker answer box */
        border: 1px solid #4a90e2;  /* Blue border for contrast */
        border-radius: 8px;
        padding: 15px;
        margin-top: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);  /* Darker shadow */
        color: #E0E0E0;          /* Light text */
    }
    .header {
        color: #E0E0E0;          /* Light text for dark mode */
        font-size: 36px;
        font-weight: bold;
        text-align: center;
    }
    .subheader {
        color: #A0A0A0;          /* Lighter gray for subheader */
        font-size: 18px;
        text-align: center;
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

tenant_id = os.getenv("TENANT_ID")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
authority = f"https://login.microsoftonline.com/{tenant_id}"
redirect_uri = "https://stdemo123-nucsd5jcnm4gdr8zvaehaw.streamlit.app/"
scopes = ["User.Read"]

# Initialize MSAL application
app = msal.ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret,
)

# Initialize session states
if "auth_flow_initiated" not in st.session_state:
    st.session_state["auth_flow_initiated"] = False

# Handle query parameters for callback after login
query_params = st.query_params
if "code" in query_params:
    try:
        # Acquire token using the authorization code
        result = app.acquire_token_by_authorization_code(
            query_params["code"],
            scopes=scopes,
            redirect_uri=redirect_uri,
        )
        
        if "access_token" in result:
            st.session_state["token"] = result["access_token"]
            st.session_state["logged_in"] = True
            if "id_token_claims" in result:
                user_info = result["id_token_claims"]
                st.session_state["user_name"] = user_info.get("name", "User")
            else:
                st.session_state["user_name"] = "User"
            
            # Clear the query parameters to prevent reprocessing
            st.query_params.clear()
            st.rerun()
        else:
            if "error" in result:
                st.error(f"Authentication error: {result.get('error')} - {result.get('error_description')}")
            else:
                st.error("Login failed. Please try again.")
    except Exception as e:
        st.error(f"An error occurred during authentication: {str(e)}")
        st.session_state["auth_flow_initiated"] = False

# Define navigation pages and styles
pages = ["Main", "Procurement Dashboard", "NL2SQL Chatbot"]
logo_url = "https://user-images.githubusercontent.com/109947291/223796328-328e1a97-fbb7-48c6-b808-17a5122993b9.png"  # Direct URL
styles = {
    "nav": {
        "background-color": "#1B5E20",  # Dark green background
        "justify-content": "center",    # Center the navbar items (kept from your app)
    },
    "div": {
        "max-width": "32rem",           # Retained from original
    },
    "span": {
        "border-radius": "0.5rem",      # Rounded corners from original
        "color": "#E0E0E0",             # Light gray text for visibility on dark green
        "margin": "0 0.125rem",         # Small margin between items from original
        "padding": "0.4375rem 0.625rem",  # Padding from original, matches your compact style
    },
    "active": {
        "background-color": "rgba(56, 142, 60, 0.8)",  # Medium green with opacity for active state
        "color": "#FFFFFF",             # White text for contrast on active state
    },
    "hover": {
        "background-color": "rgba(76, 175, 80, 0.6)",  # Lighter green with opacity for hover state
        "color": "#FFFFFF",             # White text for hover state
    }
}
options = {
    "show_menu": False,  # Hide Streamlit menu
    "show_sidebar": False,  # Hide sidebar toggle
}

# Render content based on login state
if "logged_in" in st.session_state and st.session_state["logged_in"]:
    # Render navigation bar after login
    page = st_navbar(
        pages,
        styles=styles,
        options=options,
        key="main_nav"
    )

    # Define page functions
    functions = {
        "Main": pg.show_main,
        "Procurement Dashboard": pg.show_page1,
        "NL2SQL Chatbot": pg.show_page2,
    }

    # Execute the selected page function
    go_to = functions.get(page)
    if go_to:
        go_to()
else:
    # Create login page with direct auth flow
    login_url = app.get_authorization_request_url(
        scopes,
        redirect_uri=redirect_uri,
        prompt="select_account"  # Force prompt to select account
    )
    
    # Login page
    st.markdown(
        f"""
        <div style="text-align: center; font-family: Arial, sans-serif; color: #E0E0E0; max-width: 1000px; margin: 0 auto;">
            <img src="{logo_url}" width="200" style="margin-bottom: 20px; filter: brightness(1.2); background-color: transparent;">
            <p style="font-size: 18px; margin-bottom: 20px; line-height: 1.5; color: #E0E0E0;">
                Welcome to the DataOps App. Securely log in using your Azure Active Directory credentials to explore a suite of powerful data tools designed to streamline your workflow and enhance decision-making. Below is a preview of the features awaiting you:
            </p>
            <h2 style="font-size: 24px; margin-bottom: 10px; color: #FFFFFF;">Procurement Dashboard</h2>
            <p style="font-size: 16px; line-height: 1.5; margin-bottom: 20px; color: #E0E0E0;">
                The Procurement Dashboard serves as a centralized hub for managing and analyzing your organization's procurement activities. Built with flexibility and insight in mind, it provides a detailed overview of key procurement metrics.
            </p>
            <h2 style="font-size: 24px; margin-bottom: 10px; color: #FFFFFF;">NL2SQL Chatbot</h2>
            <p style="font-size: 16px; line-height: 1.5; margin-bottom: 20px; color: #E0E0E0;">
                The NL2SQL Chatbot redefines how you interact with your data by enabling natural language queries. Whether you're a data expert or a novice, this tool makes data exploration intuitive and accessible.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Create a button that opens the Microsoft login page in the current window
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <a href="{login_url}" target="_self" style="text-decoration: none; display: block; text-align: center;">
                <button style="width: 100%; background-color: #007BFF; color: white; border: none; border-radius: 5px; padding: 12px 20px; cursor: pointer; font-size: 16px; font-weight: bold;">
                    Login with Microsoft
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )