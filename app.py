import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
from datetime import datetime

# 🌐 Firebase config
firebase_auth_config = {
    "apiKey": st.secrets["firebase_auth"]["api_key"],
    "authDomain": st.secrets["firebase_auth"]["auth_domain"],
    "databaseURL": st.secrets["firebase_auth"]["database_url"],
    "storageBucket": st.secrets["firebase_auth"]["storage_bucket"],
    "messagingSenderId": st.secrets["firebase_auth"]["messaging_sender_id"],
    "appId": st.secrets["firebase_auth"]["app_id"]
}
firebase = pyrebase.initialize_app(firebase_auth_config)
auth = firebase.auth()

# 🔐 Firebase Admin SDK init
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

# ---------------------
# 🔐 Login
# ---------------------
st.title("Login Ospedale")

if "user" not in st.session_state:
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Accedi"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.user = user
            st.rerun()
        except:
            st.error("Credenziali non valide. Riprova.")
    st.stop()

user_email = st.session_state.user["email"]
st.success(f"✅ Accesso effettuato come **{user_email}**")

# ---------------------
# 📋 Valutazione dispositivo
# ---------------------
st.header("Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# Fuzzy logic
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

# ---------------------
# 💾 Salva valutazione
# ---------------------
if st.button("Salva valutazione"):
    doc = {
        "utente": user_email,
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}"),
        "timestamp": datetime.utcnow()
    }
    db.collection("valutazioni").add(doc)
    st.success("✅ Dati salvati su Firebase!")

# ---------------------
# 📄 Visualizza valutazioni utente
# ---------------------
st.header("📊 Storico valutazioni")

valutazioni = db.collection("valutazioni").where("utente", "==", user_email).stream()

for val in valutazioni:
    data = val.to_dict()
    st.markdown(f"""
    - 📅 Data: `{data['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if 'timestamp' in data else 'N/A'}`
    - 🧪 Età: `{data['eta']} anni`
    - ⚙️ Utilizzo: `{data['utilizzo']} ore/anno`
    - 📉 Obsolescenza: `{data['obsolescenza']}`
    ---
    """)
