import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# 🔐 Controllo secrets
if "firebase" not in st.secrets or "firebase_web_api_key" not in st.secrets:
    st.error("⚠️ Configurazione Firebase mancante. Controlla i secrets.")
    st.stop()

# 🔐 Configurazione Firebase
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

API_KEY = st.secrets["firebase_web_api_key"]

# 🔌 Inizializza Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# 📦 Funzioni Firebase REST
def firebase_signin(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    res = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    return res.json()

def firebase_register(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    res = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    return res.json()

def send_email_verification(id_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}"
    res = requests.post(url, json={"requestType": "VERIFY_EMAIL", "idToken": id_token})
    return res.json()

def get_user_data(id_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={API_KEY}"
    res = requests.post(url, json={"idToken": id_token})
    return res.json()

# 🧠 Stato
if "user" not in st.session_state:
    st.session_state["user"] = None
if "id_token" not in st.session_state:
    st.session_state["id_token"] = None

# 🔐 Accesso / Registrazione
if st.session_state["user"] is None:
    st.title("🔐 Accesso Riservato")

    mode = st.radio("Modalità", ["Login", "Registrazione"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if mode == "Login":
        if st.button("Login"):
            result = firebase_signin(email, password)

            if "error" in result:
                st.error(f"Errore: {result['error']['message']}")
            else:
                user_data = get_user_data(result["idToken"])
                user_info = user_data["users"][0]

                if not user_info.get("emailVerified", False):
                    st.warning("📧 Devi prima verificare l'email.")
                    st.stop()

                # ✅ Controllo approvazione
                doc_ref = db.collection("utenti_autorizzati").document(email).get()
                if not doc_ref.exists or not doc_ref.to_dict().get("approved", False):
                    st.error("⛔ Il tuo account è in attesa di approvazione.")
                    st.stop()

                st.session_state["user"] = result["email"]
                st.session_state["id_token"] = result["idToken"]
                st.rerun()

    else:  # Registrazione
        if st.button("Registrati"):
            result = firebase_register(email, password)

            if "error" in result:
                st.error(f"Errore: {result['error']['message']}")
            else:
                send_email_verification(result["idToken"])
                # ⛔ Salva in Firestore con approvazione False
                db.collection("utenti_autorizzati").document(email).set({
                    "approved": False
                })
                st.success("✅ Registrazione completata! Controlla la tua email per verificarla.")
                st.info("Attendi l'approvazione dell'amministratore.")

    st.stop()

# ✅ Utente loggato
st.title("🏥 Valutazione Obsolescenza Dispositivo Medico")
user_email = st.session_state["user"]

# 🔓 Logout
if st.button("Logout"):
    st.session_state["user"] = None
    st.session_state["id_token"] = None
    st.rerun()

# 👮‍♀️ Admin Panel (solo per admin)
if user_email == "andreolimarco01@gmail.com":
    st.subheader("👮 Pannello di Approvazione Utenti")
    utenti = db.collection("utenti_autorizzati").where("approved", "==", False).stream()
    for u in utenti:
        u_id = u.id
        st.write(f"📧 {u_id}")
        if st.button(f"✅ Approva {u_id}", key=u_id):
            db.collection("utenti_autorizzati").document(u_id).update({"approved": True})
            st.success(f"{u_id} approvato!")
            st.rerun()

# 🎚 Input
eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# 🎛 Fuzzy logic
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

# 💾 Salvataggio su Firestore
if st.button("Salva valutazione"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Valutazione salvata!")

# 📋 Visualizzazione
st.subheader("📋 Valutazioni salvate")
valutazioni = db.collection("ospedali").document(user_email).collection("valutazioni").stream()
for doc in valutazioni:
    d = doc.to_dict()
    st.write(f"- Età: {d['eta']} | Utilizzo: {d['utilizzo']} | Obsolescenza: {d['obsolescenza']}")
