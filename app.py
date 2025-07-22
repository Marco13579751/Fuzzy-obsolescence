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

# 🛡️ Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login Ospedale")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Accedi"):
        auth_dict = st.secrets["auth"]
        if email in auth_dict and password == auth_dict[email]:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.success("✅ Login effettuato!")
            st.rerun()

        else:
            st.error("❌ Credenziali errate")
    st.stop()

# ✅ App dopo login
st.title("Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# 🎛️ Definizione fuzzy
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

# 💾 Salva nel database
if st.button("Salva valutazione"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}"),
        "ospedale": st.session_state.user_email
    }
    db.collection("valutazioni").add(doc)
    st.success("✅ Dati salvati su Firebase Firestore!")

# 📄 Visualizza valutazioni salvate
st.subheader("📊 Valutazioni precedenti")
query = db.collection("valutazioni").where("ospedale", "==", st.session_state.user_email).stream()

for doc in query:
    val = doc.to_dict()
    st.write(f"🩺 Età: {val['eta']} anni, ⏱️ Utilizzo: {val['utilizzo']} ore, 🧮 Obsolescenza: {val['obsolescenza']}")
