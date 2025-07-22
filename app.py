import streamlit as st
import numpy as np
import skfuzzy as fuzz
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore

# 🔐 Firebase config per auth (pyrebase)
firebase_auth_config = {
    "apiKey": st.secrets["firebase_auth"]["apiKey"],
    "authDomain": st.secrets["firebase_auth"]["authDomain"],
    "databaseURL": st.secrets["firebase_auth"]["databaseURL"],
    "projectId": st.secrets["firebase_auth"]["projectId"],
    "storageBucket": st.secrets["firebase_auth"]["storageBucket"],
    "messagingSenderId": st.secrets["firebase_auth"]["messagingSenderId"],
    "appId": st.secrets["firebase_auth"]["appId"]
}

firebase = pyrebase.initialize_app(firebase_auth_config)
auth = firebase.auth()

# Inizializza Firebase Admin SDK per Firestore
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
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
}

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 🔐 Login
st.title("🔐 Login Firebase")

if "user" not in st.session_state:
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.user = user
            st.success("Login effettuato con successo!")
            st.experimental_rerun()
        except Exception as e:
            st.error("Errore nel login: email o password errati.")
    st.stop()

# Logout
if st.button("Logout"):
    st.session_state.pop("user", None)
    st.success("Logout effettuato.")
    st.experimental_rerun()

# 🎯 App principale
st.title("🩺 Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

eta_range = np.arange(0, 31, 1)
uso_range = np.arange(0, 5001, 100)

giovane = fuzz.trimf(eta_range, [0, 0, 15])
vecchio = fuzz.trimf(eta_range, [10, 30, 30])
basso = fuzz.trimf(uso_range, [0, 0, 2000])
alto = fuzz.trimf(uso_range, [1000, 5000, 5000])

eta_g = fuzz.interp_membership(eta_range, giovane, eta)
eta_v = fuzz.interp_membership(eta_range, vecchio, eta)
uso_b = fuzz.interp_membership(uso_range, basso, utilizzo)
uso_a = fuzz.interp_membership(uso_range, alto, utilizzo)

obsolescenza = max(eta_v, uso_a)

st.write("**Grado di obsolescenza:**", f"{obsolescenza:.2f}")
if obsolescenza > 0.6:
    st.error("⚠️ Dispositivo potenzialmente obsoleto")
else:
    st.success("✅ Dispositivo in buone condizioni")

# 💾 Salvataggio solo se loggato
if st.button("Salva valutazione"):
    doc = {
        "email": st.session_state.user['email'],
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    db.collection("valutazioni").add(doc)
    st.success("✅ Dati salvati su Firebase Firestore!")
