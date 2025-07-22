import streamlit as st
import firebase_admin
from firebase_admin import credentials
import requests

# Inizializza Firebase Admin SDK (una sola volta)
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": st.secrets["firebase"]["type"],
        "project_id": st.secrets["firebase"]["project_id"],
        "private_key_id": st.secrets["firebase"]["private_key_id"],
        "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["firebase"]["client_email"],
        "client_id": st.secrets["firebase"]["client_id"],
        "auth_uri": st.secrets["firebase"]["auth_uri"],
        "token_uri": st.secrets["firebase"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
    })
    firebase_admin.initialize_app(cred)

API_KEY = st.secrets["firebase_web_api_key"]

def signup(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    r = requests.post(url, json=data)
    if r.status_code == 200:
        id_token = r.json()["idToken"]
        send_verification_email(id_token)
        return True, "Registrazione completata. Controlla la tua email per verificarla."
    else:
        return False, r.json().get("error", {}).get("message", "Errore durante la registrazione.")

def send_verification_email(id_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}"
    payload = {
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token
    }
    requests.post(url, json=payload)

def login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    r = requests.post(url, json=payload)
    if r.status_code == 200:
        data = r.json()
        if not data.get("emailVerified", False):
            return False, "Email non verificata. Controlla la tua casella di posta."
        return True, data
    else:
        return False, r.json().get("error", {}).get("message", "Credenziali errate.")

# Logout
if "user" in st.session_state:
    with st.sidebar:
        st.markdown(f"**Email:** {st.session_state.user['email']}")
        if st.button("Logout"):
            del st.session_state.user
            st.rerun()

if "user" not in st.session_state:
    st.title("Login / Registrazione")
    tab = st.radio("Seleziona", ["Login", "Registrati"])

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if tab == "Login":
        if st.button("Login"):
            ok, result = login(email, password)
            if ok:
                st.session_state.user = {"email": result["email"], "idToken": result["idToken"]}
                st.rerun()
            else:
                st.error(result)
    else:
        if st.button("Registrati"):
            ok, msg = signup(email, password)
            st.success(msg) if ok else st.error(msg)

else:
    st.title("Dashboard privata")
    st.success("Accesso effettuato!")
