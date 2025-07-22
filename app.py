import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase

# 🔐 Firebase Admin SDK (per Firestore)
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

# 🔑 Firebase Client SDK per autenticazione
pyrebase_config = {
    "apiKey": st.secrets["firebase"]["api_key"],
    "authDomain": st.secrets["firebase"]["auth_domain"],
    "projectId": st.secrets["firebase"]["project_id"],
    "storageBucket": st.secrets["firebase"]["storage_bucket"],
    "messagingSenderId": st.secrets["firebase"]["messaging_sender_id"],
    "appId": st.secrets["firebase"]["app_id"],
    "databaseURL": st.secrets["firebase"]["database_url"]
}
firebase = pyrebase.initialize_app(pyrebase_config)
auth = firebase.auth()

# 🧑‍⚕️ Login ospedale
st.title("Accesso Ospedale 🔐")
with st.form("login_form"):
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Accedi")

if submitted:
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        st.session_state["user"] = user
        st.success("✅ Login effettuato")
    except Exception as e:
        st.error("❌ Email o password errati")

if "user" not in st.session_state:
    st.stop()

user = st.session_state["user"]
user_id = user["localId"]  # UID univoco dell'ospedale

# ----------------------------
# Sezione principale dopo login
# ----------------------------
st.title("Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# 🎛️ Logica fuzzy
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

# 💾 Salva valutazione
if st.button("💾 Salva valutazione"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    db.collection("ospedali").document(user_id).collection("valutazioni").add(doc)
    st.success("✅ Dati salvati nel database!")

# 📊 Visualizza valutazioni
st.subheader("📂 Valutazioni salvate")
try:
    docs = db.collection("ospedali").document(user_id).collection("valutazioni").stream()
    dati = [{
        "Età (anni)": d.get("eta"),
        "Ore utilizzo": d.get("utilizzo"),
        "Obsolescenza": d.get("obsolescenza")
    } for d in docs]

    if dati:
        st.dataframe(dati)
    else:
        st.info("Nessuna valutazione presente.")
except Exception as e:
    st.error("Errore nel caricamento dati.")
