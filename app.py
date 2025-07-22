import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore

# 🔐 Configura Firebase con i segreti da secrets.toml
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

# 🔌 Inizializza Firebase una sola volta
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 👤 Autenticazione email/password
if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    st.title("🔐 Login Ospedale")
    email_input = st.text_input("Email")
    password_input = st.text_input("Password", type="password")

    if st.button("Login"):
        auth_users = dict(st.secrets["auth"])
        if email_input in auth_users and password_input == auth_users[email_input]:
            st.session_state["user"] = email_input
            st.rerun()
        else:
            st.error("❌ Credenziali errate")
    st.stop()

# ✅ Utente autenticato
st.title("Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# 🎛 Definizione fuzzy
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

# 🌟 Risultato
st.write("**Grado di obsolescenza:**", f"{obsolescenza:.2f}")
if obsolescenza > 0.6:
    st.error("⚠️ Dispositivo potenzialmente obsoleto")
else:
    st.success("✅ Dispositivo in buone condizioni")

# 🗃 Salva nel database nella collezione per ospedale (email come ID)
if st.button("Salva valutazione"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    user_email = st.session_state["user"]
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Dati salvati su Firebase Firestore!")

# 📋 Visualizzazione delle valutazioni salvate
st.subheader("📋 Valutazioni salvate")
user_email = st.session_state["user"]
valutazioni_ref = db.collection("ospedali").document(user_email).collection("valutazioni")
docs = valutazioni_ref.stream()

for doc in docs:
    dati = doc.to_dict()
    st.write(f"- Età: {dati['eta']}, Utilizzo: {dati['utilizzo']}, Obsolescenza: {dati['obsolescenza']}")
