import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# --- Configurazione e inizializzazione Firebase ---
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

API_KEY = st.secrets["firebase_web_api_key"]

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Funzioni Firebase Authentication REST ---
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

# --- Stato ---
if "user" not in st.session_state:
    st.session_state["user"] = None
if "id_token" not in st.session_state:
    st.session_state["id_token"] = None

# --- UI Autenticazione ---
if st.session_state["user"] is None:
    st.title("🔐 Login / Registration")

    mode = st.radio("Select modality", ["Login", "Registration"])
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
                    st.warning("📧 verify your email before sign in.")
                else:
                    # Verifica se utente è approvato
                    doc = db.collection("utenti_autorizzati").document(email).get()
                    if not doc.exists or not doc.to_dict().get("approved", False):
                        st.error("⛔ Utent doesn't approved. Wait for Admin approval.")
                    else:
                        st.session_state["user"] = email
                        st.session_state["id_token"] = result["idToken"]
                        st.success("✅ Accesso effettuato")
                        st.rerun()

    else:
        if st.button("Register"):
            result = firebase_register(email, password)
            if "error" in result:
                st.error(f"Errore: {result['error']['message']}")
            else:
                send_email_verification(result["idToken"])
                # Salva utente come non approvato
                db.collection("utenti_autorizzati").document(email).set({"email": email, "approved": False})
                st.success("✅ Registration completed. Check your email box for verification.")
                st.info("After verification, wait for admin approval.")
    st.stop()

# --- Logout ---
if st.button("Logout"):
    st.session_state["user"] = None
    st.session_state["id_token"] = None
    st.rerun()

# --- Dashboard ---
st.title("Dashboard Obsolescence Medical Device")

# 👮‍♂️ Se sei admin, gestisci approvazioni
if st.session_state["user"] == "andreolimarco01@gmail.com":  
    st.write("✅ Admin access")
    st.subheader("🔐 Manage regstered users")
    utenti = db.collection("utenti_autorizzati").stream()
    for u in utenti:
        dati = u.to_dict()
        email = dati.get("email", "")
        approved = dati.get("approved", False)
        col1, col2 = st.columns([3, 1])
        col1.write(f"👤 {email} - {'✅ Approved' if approved else '❌ Not approved'}")
        if not approved:
            if col2.button("Approva", key=email):
                db.collection("utenti_autorizzati").document(email).update({"approved": True})
                st.success(f"{email} approvato ✅")
                st.rerun()

# --- Input utente ---
eta = st.slider("Age of device(anni)", 0, 30, 10)
utilizzo = st.slider("Annualy hours of usage", 0, 5000, 1000)

# --- Fuzzy logic ---
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

st.write("**Obsolescence score:**", f"{obsolescenza:.2f}")
if obsolescenza > 0.6:
    st.error("⚠️ Device partially obsolet")
else:
    st.success("✅ Device in good condition")

# --- Salvataggio in Firestore ---
user_email = st.session_state["user"]
if st.button("Save valuation"):
    doc = {
        "eta": eta,
        "utilizzo": utilizzo,
        "obsolescenza": float(f"{obsolescenza:.2f}")
    }
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Valutation saved!")

# --- Visualizzazione valutazioni salvate ---
st.subheader("📋 Valutations saved")
valutazioni = db.collection("ospedali").document(user_email).collection("valutazioni").stream()
for doc in valutazioni:
    d = doc.to_dict()
    st.write(f"- Age: {d['eta']} | Annual usage: {d['utilizzo']} | Obsolescence: {d['obsolescenza']}")

# --- Aggiunta dispositivo medico ---
st.subheader("➕ Aggiungi nuovo dispositivo medico")

with st.form("add_device"):
    col1, col2, col3 = st.columns(3)
    with col1:
        ID_DM = st.number_input("ID_DM", min_value=1, step=1)
        ID_Categoria_III = st.text_input("Cat. III", max_chars=5)
        Tipo_Utilizzo = st.text_input("Tipo utilizzo", max_chars=255)
        Marca = st.text_input("Marca", max_chars=255)
    with col2:
        ID_Padre = st.number_input("ID_Padre", min_value=0, step=1)
        ID_Categoria_IV = st.text_input("Cat. IV", max_chars=7)
        Livello_Criticita = st.text_input("Criticità", max_chars=255)
        Modello = st.text_input("Modello", max_chars=255)
    with col3:
        ID_Stanza = st.text_input("Stanza", max_chars=15)
        ID_Categoria_V = st.text_input("Cat. V", max_chars=13)
        Costo = st.number_input("Costo (€)", min_value=0.0, step=0.01, format="%.2f")
        Presente = st.checkbox("Presente")

    Descrizione = st.text_input("Descrizione", max_chars=255)
    Classe = st.text_input("Classe", max_chars=255)
    Capitolato = st.file_uploader("📎 Allegato capitolato (PDF, ecc.)")

    submitted = st.form_submit_button("💾 Salva dispositivo")

    if submitted:
        capitolato_bytes = Capitolato.read() if Capitolato else None
        dispositivo = {
            "ID_DM": ID_DM,
            "ID_Padre": ID_Padre,
            "ID_Stanza": ID_Stanza,
            "ID_Categoria_III": ID_Categoria_III,
            "ID_Categoria_IV": ID_Categoria_IV,
            "ID_Categoria_V": ID_Categoria_V,
            "Descrizione": Descrizione,
            "Classe": Classe,
            "Tipo_Utilizzo": Tipo_Utilizzo,
            "Livello_Criticità": Livello_Criticita,
            "Costo": Costo,
            "Presente": Presente,
            "Marca": Marca,
            "Modello": Modello,
            "Capitolato": capitolato_bytes
        }

        db.collection("dispositivi_medici").document(str(ID_DM)).set(dispositivo)
        st.success("📦 Dispositivo medico salvato con successo!")
