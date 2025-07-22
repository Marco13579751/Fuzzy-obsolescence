import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore

# 🔐 Configura Firebase
firebase_config = {
    "type": st.secrets["firebase"]["type"],
    "project_id": st.secrets["firebase"]["project_id"],
    "private_key_id": st.secrets["firebase"]["private_key_id"],
    "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
    "client_email": st.secrets["firebase"]["client_email"],
    "client_id": st.secrets["firebase"]["client_id"],
    "auth_uri": st.secrets["firebase"]["auth_uri"],
    "token_uri": st.secrets["firebase"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
    "universe_domain": st.secrets["firebase"]["universe_domain"]
}

# 🔌 Inizializza Firebase una volta sola
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 🧠 Session state per il login
if "utente" not in st.session_state:
    st.session_state.utente = None

# 🔐 Login
if st.session_state.utente is None:
    st.title("Login Ospedale")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Accedi"):
        auth_dict = st.secrets["auth"]
        if email in auth_dict and password == auth_dict[email]:
            st.session_state.utente = email
            st.success("✅ Accesso effettuato")
            st.experimental_rerun()
        else:
            st.error("❌ Credenziali errate")
    st.stop()

# ✅ App principale (dopo login)
st.title("Valutazione Obsolescenza Dispositivo Medico")

# Input
eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# Fuzzy logic
eta_range = np.arange(0, 31, 1)
uso_range = np.arange(0, 5001, 100)

giovane = fuzz.trimf(eta_range, [0, 0, 15])
vecchio = fuzz.trimf(eta_range, [10, 30, 30])
basso = fuzz.trimf(uso_range, [0, 0,]()_

