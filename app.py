import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase

# 🔐 Configura pyrebase per autenticazione
firebase_auth_config = {
    "apiKey": st.secrets["firebase_auth"]["apiKey"],
    "authDomain": st.secrets["firebase_auth"]["authDomain"],
    "projectId": st.secrets["firebase"]["project_id"],
    "storageBucket": st.secrets["firebase_auth"]["storageBucket"],
    "messagingSenderId": st.secrets["firebase_auth"]["messagingSenderId"],
    "appId": st.secrets["firebase_auth"]["appId"],
    "databaseURL": ""
}
firebase = pyrebase.initialize_app(firebase_auth_config)
auth = firebase.auth()

# 🔌 Inizializza Firebase Admin (per Firestore)
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

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 🌐 Autenticazione
st.title("Login Utente")

if "user" not in st.session_state:
    scelta = st.radio("Seleziona:", ["Login", "Registrati"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if scelta == "Registrati":
        if st.button("Crea account"):
            try:
                auth.create_user_with_email_and_password(email, password)
                st.success("Registrazione riuscita. Ora effettua il login.")
            except:
                st.error("Errore nella registrazione.")
    else:
        if st.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state.user = user
                st.success("Login effettuato!")
            except:
                st.error("Credenziali non valide.")
else:
    user = st.session_state.user
    st.success(f"Utente connesso: {user['email']}")

    # 📌 Interfaccia utente
    st.header("Valutazione Obsolescenza Dispositivo Medico")

    eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
    utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

    # 🎛️ Definizione fuzzy
    eta_range = np.arange(0, 31, 1)
    uso_range = np.arange(0, 5001, 100)

    giovane = fuzz.trimf(eta_range, [0, 0, 15])
    vecchio = fuzz.trimf(eta_range, [10, 30, 30])
    basso = fuzz.trimf(uso_range, [0, 0, 2000])
    alto = fuzz.trimf(uso_range, [1000, 5000, 5000])

    eta_v = fuzz.interp_membership(eta_range, vecchio, eta)
    uso_a = fuzz.interp_membership(uso_range, alto, utilizzo)

    obsolescenza = max(eta_v, uso_a)

    # 🎯 Risultato
    st.write("**Grado di obsolescenza:**", f"{obsolescenza:.2f}")
    if obsolescenza > 0.6:
        st.error("⚠️ Dispositivo potenzialmente obsoleto")
    else:
        st.success("✅ Dispositivo in buone condizioni")

    # 💾 Salva nel database
    if st.button("Salva valutazione"):
        doc = {
            "email": user["email"],
            "eta": eta,
            "utilizzo": utilizzo,
            "obsolescenza": float(f"{obsolescenza:.2f}")
        }
        db.collection("valutazioni").add(doc)
        st.success("✅ Dati salvati nel database Firebase!")
