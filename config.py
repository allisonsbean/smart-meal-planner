import streamlit as st

# Try to get from Streamlit secrets first (for deployment), then fallback to local values
try:
    KROGER_CLIENT_ID = st.secrets["KROGER_CLIENT_ID"]
    KROGER_CLIENT_SECRET = st.secrets["KROGER_CLIENT_SECRET"] 
    SPOONACULAR_API_KEY = st.secrets["SPOONACULAR_API_KEY"]
    ZIP_CODE = st.secrets["ZIP_CODE"]
    KROGER_BASE_URL = st.secrets["KROGER_BASE_URL"]
except:
    # Fallback for local development
    KROGER_CLIENT_ID = "beansmeals-bbc7nxcc"
    KROGER_CLIENT_SECRET = "BQLtwVhPhFMIHGPaZMKHe35YNtPsrK5cLdJ0fJdq"
    SPOONACULAR_API_KEY = "566f8556333e4212ba2af19da916482d"
    ZIP_CODE = "24712"
    KROGER_BASE_URL = "https://api.kroger.com"
