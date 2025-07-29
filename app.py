import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd

# -- Configurazione e inizializzazione Firebase ---
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
    st.title("🏥 Sistema di Valutazione Obsolescenza Dispositivi Medici")
    st.markdown("Benvenuto. Accedi o registrati per utilizzare la piattaforma.")

    mode = st.radio("Seleziona modalità", ["Login", "Registrazione"])
    email = st.text_input("Email istituzionale")
    password = st.text_input("Password", type="password")

    if mode == "Login":
        if st.button("Accedi"):
            result = firebase_signin(email, password)
            if "error" in result:
                st.error(f"Errore: {result['error']['message']}")
            else:
                user_data = get_user_data(result["idToken"])
                user_info = user_data["users"][0]

                if not user_info.get("emailVerified", False):
                    st.warning("📧 Verifica la tua email prima di accedere.")
                else:
                    doc = db.collection("utenti_autorizzati").document(email).get()
                    if not doc.exists or not doc.to_dict().get("approved", False):
                        st.error("⛔ Utente non approvato. Attendere l'approvazione dell'amministratore.")
                    else:
                        st.session_state["user"] = email
                        st.session_state["id_token"] = result["idToken"]
                        st.success("✅ Accesso effettuato")
                        st.rerun()

    else:
        if st.button("Registrati"):
            result = firebase_register(email, password)
            if "error" in result:
                st.error(f"Errore: {result['error']['message']}")
            else:
                send_email_verification(result["idToken"])
                db.collection("utenti_autorizzati").document(email).set({"email": email, "approved": False})
                st.success("✅ Registrazione completata. Verifica la tua email.")
                st.info("Dopo la verifica, attendi l'approvazione da parte dell'amministratore.")
    st.stop()

# --- Logout ---
with st.sidebar:
    st.write(f"👤 Utente: {st.session_state['user']}")
    if st.button("Logout"):
        st.session_state["user"] = None
        st.session_state["id_token"] = None
        st.rerun()

# --- Dashboard ---
st.title("📊 Pannello di Valutazione Dispositivi")

if st.session_state["user"] == "andreolimarco01@gmail.com":  
    st.subheader("🔐 Gestione utenti registrati")
    utenti = db.collection("utenti_autorizzati").stream()
    for u in utenti:
        dati = u.to_dict()
        email = dati.get("email", "")
        approved = dati.get("approved", False)
        col1, col2 = st.columns([3, 1])
        col1.write(f"👤 {email} - {'✅ Approvato' if approved else '❌ Non approvato'}")
        if not approved:
            if col2.button("Approva", key=email):
                db.collection("utenti_autorizzati").document(email).update({"approved": True})
                st.success(f"{email} approvato ✅")
                st.rerun()

# --- Input utente ---
st.subheader("📥 Inserimento dati dispositivo medico")
st.divider()

parametri_nome = [
    "Età del dispositivo (anni)",
    "Ore di utilizzo annuali",
    "Numero di manutenzioni/anno",
    "Numero guasti registrati",
    "Costo medio riparazioni (€)",
    "Percentuale utilizzo giornaliero (%)",
    "Livello di aggiornamento software (%)",
    "Supporto del produttore disponibile (0-1)",
    "Facilità reperimento pezzi (0-1)",
    "Consumo energetico (kWh)",
    "Compatibilità con sistemi moderni (0-1)",
    "Numero utenti formati",
    "Livello soddisfazione utente (0-10)"
]

inputs = []
cols = st.columns(3)

for i, nome in enumerate(parametri_nome):
    col = cols[i % 3]
    val = col.text_input(f"{nome}", value="", key=f"param_{i+1}")
    try:
        parsed = float(val) if val.strip() != "" else None
    except ValueError:
        parsed = None
    inputs.append(parsed)

# --- Fuzzy logic ---
def fuzzy_membership(val, low_range, high_range):
    if val is None:
        return 0
    x = np.linspace(low_range[0], high_range[2], 1000)
    low_mf = fuzz.trimf(x, low_range)
    high_mf = fuzz.trimf(x, high_range)
    low = fuzz.interp_membership(x, low_mf, val)
    high = fuzz.interp_membership(x, high_mf, val)
    return max(low, high)

fuzzy_ranges = [
    ([0, 0, 10], [8, 20, 30]),
    ([0, 0, 1000], [800, 3000, 5000]),
    ([0, 0, 2], [1, 5, 10]),
    ([0, 0, 2], [1, 5, 10]),
    ([0, 0, 100], [50, 300, 1000]),
    ([0, 0, 30], [20, 60, 100]),
    ([0, 0, 30], [20, 60, 100]),
    ([0, 0, 0.3], [0.2, 0.6, 1]),
    ([0, 0, 0.3], [0.2, 0.6, 1]),
    ([0, 0, 100], [50, 150, 500]),
    ([0, 0, 0.3], [0.2, 0.6, 1]),
    ([0, 0, 5], [3, 8, 20]),
    ([0, 0, 3], [2, 6, 10]),
]

membership_values = [fuzzy_membership(val, ranges[0], ranges[1]) for val, ranges in zip(inputs, fuzzy_ranges)]
obsolescenza = (
    sum(membership_values) / len([v for v in membership_values if v > 0])
    if any(membership_values)
    else None
)

st.divider()

if obsolescenza is not None:
    st.metric(label="Indice di Obsolescenza", value=f"{obsolescenza:.2f}")
    if obsolescenza > 0.6:
        st.error("⚠️ Il dispositivo presenta un elevato livello di obsolescenza.")
    elif obsolescenza > 0.3:
        st.warning("🟡 Obsolescenza moderata.")
    else:
        st.success("✅ Il dispositivo è in buone condizioni.")
else:
    st.info("🟡 Inserire almeno un parametro valido per calcolare lo score.")

# --- Salvataggio in Firestore ---
user_email = st.session_state["user"]
if st.button("💾 Salva valutazione"):
    doc = {
        "parametri": inputs,
        "obsolescenza": float(f"{obsolescenza:.2f}") if obsolescenza is not None else None
    }
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Valutazione salvata con successo.")

# --- Visualizzazione valutazioni salvate ---
st.subheader("📋 Storico valutazioni")
valutazioni = db.collection("ospedali").document(user_email).collection("valutazioni").stream()
for doc in valutazioni:
    d = doc.to_dict()
    params = d.get("parametri", ["N/D"]*13)
    score = d.get("obsolescenza", "N/D")
    st.write(f"- Parametri: {params} | Obsolescenza: {score}")



