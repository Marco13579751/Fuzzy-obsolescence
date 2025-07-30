import streamlit as st
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import IPython.display as display


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

# --- Input utente con 13 parametri opzionali e nomi specifici ---
st.subheader("📥 Add Device's informations")

parametri_nome = [
    'normalizedAge', 'normalizedRiskLevels', 'normalizedfunctionLevels',
    'normalizedStateLevels', 'normalizedLifeResLevels', 'normalizedObsLevels',
    'normalizedUtilizationLevels', 'normalizedUptime',
    'normalizedfaultRateLevels', 'normalizedEoLS'
]
parametri_nome_prova_con_2_parametri=['normalizedAge','normalizedfaultRateLevels']

inputs = []

# Mostra i box in righe da 3 colonne
colonne = st.columns(3)

for i, nome in enumerate(parametri_nome_prova_con_2_parametri):
    col = colonne[i % 3]  # scegli la colonna ciclicamente
    with col:
        val = st.number_input(
            f"{nome}",
            min_value=0.0,
            max_value=1.0,
            step=0.1,
            format="%.2f",
            key=f"param_{i+1}"
        )
        inputs.append(val if val != 0.0 else None)


# --- Fuzzy logic ---
normalized_age = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedAge')
normalized_risk_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedRiskLevels')
normalized_function_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedfunctionLevels')
normalized_state_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedStateLevels')
normalized_life_res_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedLifeResLevels')
normalized_obs_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedObsLevels')
normalized_utilization_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedUtilizationLevels')
normalized_uptime = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedUptime')
normalized_fault_rate_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedfaultRateLevels')
normalized_eols = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedEoLS')


# Add output variable (Consequent)
criticity = ctrl.Consequent(np.arange(0, 10.1, 0.1), 'Criticity')

# Define membership functions for normalizedAge

normalized_age['New'] = fuzz.trapmf(normalized_age.universe, [0, 0, 0.3, 0.4])
normalized_age['Middle'] = fuzz.trimf(normalized_age.universe, [0.3, 0.5, 0.7])
normalized_age['Old'] = fuzz.trapmf(normalized_age.universe, [0.6, 0.8, 1, 1])

# Define membership functions for normalizedRiskLevels
normalized_risk_levels['NotSignificant'] = fuzz.trapmf(normalized_risk_levels.universe, [0, 0, 0.1, 0.2])
normalized_risk_levels['NonPermanent'] = fuzz.trimf(normalized_risk_levels.universe, [0.15, 0.2, 0.25])
normalized_risk_levels['ErrataTherapy'] = fuzz.trimf(normalized_risk_levels.universe, [0.25, 0.35, 0.45])
normalized_risk_levels['Permanent'] = fuzz.trapmf(normalized_risk_levels.universe, [0.45, 0.55, 0.65, 0.75])
normalized_risk_levels['Death'] = fuzz.trapmf(normalized_risk_levels.universe, [0.75, 0.80, 0.90, 1])

# Define membership functions for normalizedfunctionLevels
normalized_function_levels['LowIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0, 0, 0.1, 0.2])
normalized_function_levels['MidLowIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.15, 0.2, 0.25])
normalized_function_levels['MidIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.25, 0.35, 0.45])
normalized_function_levels['MidHighIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0.45, 0.55, 0.65, 0.75])
normalized_function_levels['HighIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.7, 0.8, 0.9])
normalized_function_levels['VeryHighIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0.85, 1, 1, 1])

# Define membership functions for normalizedStateLevels
normalized_state_levels['Buono'] = fuzz.trapmf(normalized_state_levels.universe, [0, 0, 0.1, 0.2])
normalized_state_levels['Sufficiente'] = fuzz.trimf(normalized_state_levels.universe, [0.15, 0.2, 0.25])
normalized_state_levels['Deteriorato'] = fuzz.trimf(normalized_state_levels.universe, [0.25, 0.35, 0.45])
normalized_state_levels['Degradato'] = fuzz.trapmf(normalized_state_levels.universe, [0.45, 0.55, 0.75, 1])

# Define membership functions for normalizedLifeResLevels
normalized_life_res_levels['BrandNew'] = fuzz.trimf(normalized_life_res_levels.universe, [0, 0, 0.2])
normalized_life_res_levels['Recent'] = fuzz.trimf(normalized_life_res_levels.universe, [0.15, 0.3, 0.45])
normalized_life_res_levels['FairlyNew'] = fuzz.trimf(normalized_life_res_levels.universe, [0.4, 0.55, 0.7])
normalized_life_res_levels['UsedButGoodCondition'] = fuzz.trimf(normalized_life_res_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedUtilizationLevels
normalized_utilization_levels['Stock'] = fuzz.trimf(normalized_utilization_levels.universe, [0, 0, 0.2])
normalized_utilization_levels['Unused'] = fuzz.trimf(normalized_utilization_levels.universe, [0.15, 0.3, 0.45])
normalized_utilization_levels['RarelyUsed'] = fuzz.trimf(normalized_utilization_levels.universe, [0.4, 0.55, 0.7])
normalized_utilization_levels['ContinuousUse'] = fuzz.trimf(normalized_utilization_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedObsLevels
normalized_obs_levels['StateOfTheArt'] = fuzz.trimf(normalized_obs_levels.universe, [0, 0, 0.2])
normalized_obs_levels['UsableWithRemainingLifeLessThan0'] = fuzz.trimf(normalized_obs_levels.universe, [0.15, 0.3, 0.45])
normalized_obs_levels['UsableWithRemainingLifeGreaterOrEqual0'] = fuzz.trimf(normalized_obs_levels.universe, [0.4, 0.55, 0.7])
normalized_obs_levels['Obsolete'] = fuzz.trimf(normalized_obs_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedUptime

normalized_uptime['Max'] = fuzz.trapmf(normalized_uptime.universe, [0.6, 0.8, 1, 1])
normalized_uptime['Middle'] = fuzz.trimf(normalized_uptime.universe, [0.3, 0.5, 0.7])
normalized_uptime['Min'] = fuzz.trapmf(normalized_uptime.universe, [0, 0, 0.2, 0.4])

# Define membership functions for normalizedfaultRateLevels
normalized_fault_rate_levels['NeverExceeded'] = fuzz.trapmf(normalized_fault_rate_levels.universe, [0, 0, 0.25, 0.5])
normalized_fault_rate_levels['ExceededLifetimeNotRecent'] = fuzz.trimf(normalized_fault_rate_levels.universe, [0.25, 0.5, 0.75])
normalized_fault_rate_levels['ExceededRecentlyNotLifetime'] = fuzz.trimf(normalized_fault_rate_levels.universe, [0.5, 0.75, 1])
normalized_fault_rate_levels['ExceededLifetimeAndRecent'] = fuzz.trapmf(normalized_fault_rate_levels.universe, [0.75, 1, 1, 1])

# Define membership functions for normalizedEoLS
normalized_eols['Absent'] = fuzz.trimf(normalized_eols.universe, [0, 0, 0.125])
normalized_eols['PresentEoLBeforeToday'] = fuzz.trapmf(normalized_eols.universe, [0.25, 0.375, 0.625, 0.75])
normalized_eols['PresentEoSAfterToday'] = fuzz.trapmf(normalized_eols.universe, [0.5, 0.625, 0.875, 1])
normalized_eols['PresentEoSBeforeToday'] = fuzz.trimf(normalized_eols.universe, [0.75, 0.875, 1])

# Define membership functions for Criticity
criticity['VeryLow'] = fuzz.trapmf(criticity.universe, [0, 0, 1, 2]) # Adjusted range to match 0-10 scale
criticity['Low'] = fuzz.trapmf(criticity.universe, [1.5, 2.5, 3.5, 4.5]) # Adjusted range
criticity['Medium'] = fuzz.trimf(criticity.universe, [4, 5, 6]) # Adjusted range
criticity['High'] = fuzz.trapmf(criticity.universe, [5.5, 6.5, 7.5, 8.5]) # Adjusted range
criticity['VeryHigh'] = fuzz.trapmf(criticity.universe, [8, 9, 10, 10]) # Adjusted range

# Define fuzzy rules
rules = [
    ctrl.Rule(normalized_age['New'], criticity['VeryLow']),
    ctrl.Rule(normalized_age['New'], criticity['Low']), # This rule seems to contradict the previous one
    ctrl.Rule(normalized_age['Middle'], criticity['Medium']),
    ctrl.Rule(normalized_age['Old'], criticity['High']),
    ctrl.Rule(normalized_age['Old'], criticity['VeryHigh']), # This rule seems to contradict the previous one
    
   
    
    ctrl.Rule(normalized_fault_rate_levels['NeverExceeded'], criticity['VeryLow']),
    ctrl.Rule(normalized_fault_rate_levels['ExceededLifetimeNotRecent'], criticity['Medium']),
    ctrl.Rule(normalized_fault_rate_levels['ExceededRecentlyNotLifetime'], criticity['Medium']),
    ctrl.Rule(normalized_fault_rate_levels['ExceededLifetimeAndRecent'], criticity['VeryHigh']),
    

]
'''
ctrl.Rule(normalized_eols['Absent'], criticity['VeryLow']),
ctrl.Rule(normalized_eols['PresentEoLBeforeToday'], criticity['High']),
    ctrl.Rule(normalized_eols['PresentEoSAfterToday'], criticity['High']),
    ctrl.Rule(normalized_eols['PresentEoSBeforeToday'], criticity['VeryHigh'])
    '''
 ''' ctrl.Rule(normalized_risk_levels['NotSignificant'], criticity['VeryLow']),
    ctrl.Rule(normalized_risk_levels['NonPermanent'], criticity['Low']),
    ctrl.Rule(normalized_risk_levels['ErrataTherapy'], criticity['Medium']),
    ctrl.Rule(normalized_risk_levels['Permanent'], criticity['High']),
    ctrl.Rule(normalized_risk_levels['Death'], criticity['VeryHigh']),

    ctrl.Rule(normalized_function_levels['LowIntensity'], criticity['VeryLow']),
    ctrl.Rule(normalized_function_levels['MidLowIntensity'], criticity['Low']),
    ctrl.Rule(normalized_function_levels['MidIntensity'], criticity['Medium']),
    ctrl.Rule(normalized_function_levels['MidHighIntensity'], criticity['High']),
    ctrl.Rule(normalized_function_levels['HighIntensity'], criticity['VeryHigh']),
    ctrl.Rule(normalized_function_levels['VeryHighIntensity'], criticity['VeryHigh']),

    ctrl.Rule(normalized_state_levels['Buono'], criticity['VeryLow']),
    ctrl.Rule(normalized_state_levels['Sufficiente'], criticity['Medium']),
    ctrl.Rule(normalized_state_levels['Deteriorato'], criticity['High']),
    ctrl.Rule(normalized_state_levels['Degradato'], criticity['VeryHigh']),

    ctrl.Rule(normalized_life_res_levels['BrandNew'], criticity['VeryLow']),
    ctrl.Rule(normalized_life_res_levels['Recent'], criticity['Low']),
    ctrl.Rule(normalized_life_res_levels['FairlyNew'], criticity['Medium']),
    ctrl.Rule(normalized_life_res_levels['UsedButGoodCondition'], criticity['High']),

    ctrl.Rule(normalized_utilization_levels['Stock'], criticity['VeryLow']),
    ctrl.Rule(normalized_utilization_levels['Unused'], criticity['Low']),
    ctrl.Rule(normalized_utilization_levels['RarelyUsed'], criticity['Medium']),
    ctrl.Rule(normalized_utilization_levels['ContinuousUse'], criticity['High']),

    ctrl.Rule(normalized_obs_levels['StateOfTheArt'], criticity['VeryLow']),
    ctrl.Rule(normalized_obs_levels['UsableWithRemainingLifeLessThan0'], criticity['Low']),
    ctrl.Rule(normalized_obs_levels['UsableWithRemainingLifeGreaterOrEqual0'], criticity['Medium']),
    ctrl.Rule(normalized_obs_levels['Obsolete'], criticity['High']),

    ctrl.Rule(normalized_uptime['Min'], criticity['VeryHigh']),
    ctrl.Rule(normalized_uptime['Middle'], criticity['Medium']),
    ctrl.Rule(normalized_uptime['Max'], criticity['VeryLow']), '''

# Create the control system (this is the equivalent of the fuzzy system in Matlab)
criticity_ctrl = ctrl.ControlSystem(rules)


plt.style.use("seaborn-v0_8-muted")  # oppure 'ggplot', 'seaborn-darkgrid', ecc.

def plot_membership_functions(antecedent, title):
    fig, ax = plt.subplots(figsize=(5, 2.5))  # Ridotto
    colors = plt.cm.viridis(np.linspace(0, 1, len(antecedent.terms)))

    for idx, term in enumerate(antecedent.terms):
        ax.plot(
            antecedent.universe,
            antecedent[term].mf,
            label=term.capitalize(),
            linewidth=1,
            color=colors[idx]
        )

    ax.set_title(title, fontsize=9, weight='bold', pad=10)
    ax.set_xlabel("Valore", fontsize=6)
    ax.set_ylabel("Appartenenza", fontsize=6)
    ax.tick_params(labelsize=6)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, fontsize=8, frameon=False)
    fig.tight_layout()

    st.pyplot(fig)
    plt.close(fig)

# Esempio di chiamata
plot_membership_functions(normalized_age, 'Age')
plot_membership_functions(normalized_risk_levels, 'Risk Levels')


# Create a simulation object for the fuzzy control system
criticity_simulation = ctrl.ControlSystemSimulation(criticity_ctrl)

# Initialize a list to store the calculated criticities
criticities = []

# Calculate criticity for each device
# Set input values for the current device
criticity_simulation.input['normalizedAge'] =parametri_nome[0]
criticity_simulation.input['normalizedRiskLevels'] = parametri_nome[1]
criticity_simulation.input['normalizedfunctionLevels'] = parametri_nome[2]
criticity_simulation.input['normalizedStateLevels'] = parametri_nome[3]
criticity_simulation.input['normalizedLifeResLevels'] = parametri_nome[4]
criticity_simulation.input['normalizedObsLevels'] = parametri_nome[5]
criticity_simulation.input['normalizedUtilizationLevels'] = parametri_nome[6]
criticity_simulation.input['normalizedUptime'] = parametri_nome[7]
criticity_simulation.input['normalizedfaultRateLevels'] = parametri_nome[8]
criticity_simulation.input['normalizedEoLS'] = parametri_nome[9]

for nome, val in zip(parametri_nome, inputs):
    criticity_simulation.input[nome] = val if val is not None else 0.0
    
# Compute the fuzzy output (Criticity)
criticity_simulation.compute()

def show_fuzzy_output(fuzzy_var, sim):
    sim.compute()
    output_value = sim.output[fuzzy_var.label]

    fig, ax = plt.subplots(figsize=(5, 2.5))
    colors = plt.cm.viridis(np.linspace(0, 1, len(fuzzy_var.terms)))

    x = fuzzy_var.universe

    for idx, term in enumerate(fuzzy_var.terms):
        mf = fuzzy_var[term].mf
        y = mf

        # Plot della curva completa
        ax.plot(x, y, label=term.capitalize(), linewidth=1, color=colors[idx])

        # Calcolo grado di attivazione del termine
        activation = fuzz.interp_membership(x, y, output_value)

        # Riempiamo solo fino al grado di attivazione
        ax.fill_between(x, 0, np.fmin(activation, y), alpha=0.4, color=colors[idx])

    # Linea verticale sul valore defuzzificato
    ax.axvline(x=output_value, color='red', linestyle='--', linewidth=1,
               label=f'Uscita = {output_value:.2f}')

    # Stile coerente
    ax.set_title(f"Output fuzzy: {fuzzy_var.label.capitalize()}", fontsize=9, weight='bold', pad=10)
    ax.set_xlabel("Valore", fontsize=6)
    ax.set_ylabel("Appartenenza", fontsize=6)
    ax.tick_params(labelsize=6)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, fontsize=8, frameon=False)
    fig.tight_layout()

    st.pyplot(fig)
    plt.close(fig)
show_fuzzy_output(criticity, criticity_simulation)



# Store the result (scaled by 10 as in your Matlab code)
obsolescenza = criticity_simulation.output['Criticity'] * 10


if obsolescenza is not None:
    st.write("**Obsolescence score:**", f"{obsolescenza:.2f}")
    if obsolescenza > 0.6:
        st.error("⚠️ Device partially obsolet")
    else:
        st.success("✅ Device in good condition")
else:
    st.info("🟡 Inserisci almeno un parametro per calcolare lo score")

# --- Salvataggio in Firestore ---
user_email = st.session_state["user"]
if st.button("Save valuation"):
    parametri_dict = {
    nome: val if val is not None else None
    for nome, val in zip(parametri_nome, inputs)
    }

    doc = {
        "parametri": parametri_dict,
        "obsolescenza": float(f"{obsolescenza:.2f}") if obsolescenza is not None else None
    }
    
 
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Valutation saved!")

# --- Visualizzazione valutazioni salvate ---
st.subheader("📋 Valutations saved")
valutazioni = db.collection("ospedali").document(user_email).collection("valutazioni").stream()
for doc in valutazioni:
    d = doc.to_dict()
    params = d.get("parametri", ["N/D"]*13)
    score = d.get("obsolescenza", "N/D")
    st.write(f"- Parametri: {params} | Obsolescence: {score}")




