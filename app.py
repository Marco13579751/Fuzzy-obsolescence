import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore

# Autenticazione semplice ospedale
with st.sidebar:
    st.header("Login Ospedale")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

logged_in = False
ospedale_id = None

if login_btn:
    for key in st.secrets["auth"]:
        if key.endswith("_email") and st.secrets["auth"][key] == email:
            user_prefix = key.replace("_email", "")
            if st.secrets["auth"].get(f"{user_prefix}_password") == password:
                logged_in = True
                ospedale_id = user_prefix
                st.success(f"✅ Accesso effettuato come {ospedale_id}")
                break
    if not logged_in:
        st.error("❌ Credenziali non valide")

# Blocca tutto se non loggato
if not logged_in:
    st.stop()

# Configura Firebase
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

# UI valutazione
st.title("Valutazione Obsolescenza Dispositivo Medico")

eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# Def fuzzy
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

# Salva valutazione
if st.button("Salva valutazione"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    db.collection(f"valutazioni_{ospedale_id}").add(doc)
    st.success("✅ Dati salvati nel database!")

# Visualizza valutazioni
st.subheader("📊 Valutazioni precedenti")
valutazioni = db.collection(f"valutazioni_{ospedale_id}").stream()

for v in valutazioni:
    d = v.to_dict()
    st.write(f"🩺 Età: {d['eta']} anni | 🕓 Utilizzo: {d['utilizzo']} ore | ⚙️ Obsolescenza: {d['obsolescenza']}")
