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
import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode


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
parametri_nome_prova_con_2_parametri=['normalized_age','normalized_fault_rate_levels','cost_levels','failure_rate','up_time']

inputs = []

if st.button("🔄 Clear cache & refresh"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
    
# Mostra i box in righe da 3 colonne
colonne = st.columns(3)

for i, nome in enumerate(parametri_nome_prova_con_2_parametri):
    col = colonne[i % 3]
    with col:
        if nome == "normalized_age":
            data_acquisto = st.date_input("Date of purchase")
            oggi = datetime.date.today()
            eta_giorni = (oggi - data_acquisto).days
            eta = eta_giorni / 365
            val = eta
            st.write(f"Age: {eta:.2f}")

        elif nome == "normalized_fault_rate_levels":
            # menu a tendina per failure rate (senza normalizzazione)
            val = st.selectbox(
                "Equipment function",
                options=[1, 2, 3, 4],
                key=f"failure_rate_{i}"
            )
        elif nome=="cost_levels" :
            val = st.number_input(
                "Cost",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key=f"cost_{i}"
            )
        elif nome=="up_time" :
            val = st.number_input(
                "Uptime",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key=f"up_time_{i}"
            )
        elif nome=="failure_rate" :
            val = st.number_input(
                "Failure rate",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key=f"failure_{i}"
            )
            

        inputs.append(val if val != 0.0 else None)



# --- Fuzzy logic ---
normalized_age = ctrl.Antecedent(np.arange(0, 11, 0.1), 'normalized_age')
failure_rate=ctrl.Antecedent(np.arange(0, 1, 0.1), 'failure_rate')

normalized_fault_rate_levels = ctrl.Antecedent(np.arange(0, 4, 0.01), 'normalized_fault_rate_levels')
up_time=ctrl.Antecedent(np.arange(0,36,0.01),'up_time')

cost_levels=ctrl.Antecedent(np.arange(0,1001,1),'cost_levels')
    
#Categorie madre
reliability=ctrl.Consequent(np.arange(0,10.1, 0.01), 'reliability')
mission=ctrl.Consequent(np.arange(0,10.1, 0.01), 'mission')
reliability_result = ctrl.Antecedent(np.arange(0, 10.1, 0.01), 'reliability_result')
mission_result = ctrl.Antecedent(np.arange(0, 10.1, 0.01), 'mission_result')

# Add output variable (Consequent)
criticity = ctrl.Consequent(np.arange(0, 10.1, 0.01), 'criticity')



# Define membership functions for normalizedAge

normalized_age['New'] = fuzz.trapmf(normalized_age.universe, [0, 0, 2, 5])
normalized_age['Middle'] = fuzz.trimf(normalized_age.universe, [3, 5, 7])
normalized_age['Old'] = fuzz.trapmf(normalized_age.universe, [5, 8, 10, 10])

failure_rate['Low'] = fuzz.trimf(failure_rate.universe, [0, 0.20,0.40])
failure_rate['Medium'] = fuzz.trimf(failure_rate.universe, [0.20,0.50,0.80])
failure_rate['High'] = fuzz.trimf(failure_rate.universe, [0.60, 0.80, 1])

#normalized_age['New'] = fuzz.gaussmf(normalized_age.universe, 2, 1)
#normalized_age['Middle'] = fuzz.gaussmf(normalized_age.universe, 5, 1)
#normalized_age['Old'] = fuzz.gaussmf(normalized_age.universe, 8, 1)

# Define membership functions for normalizedfaultRateLevels
normalized_fault_rate_levels['Under trh'] = fuzz.gaussmf(normalized_fault_rate_levels.universe, 1, 0.1)
normalized_fault_rate_levels['Around trh'] = fuzz.gaussmf(normalized_fault_rate_levels.universe, 2, 0.1)
normalized_fault_rate_levels['Above trh'] = fuzz.gaussmf(normalized_fault_rate_levels.universe, 3, 0.1)

up_time['Low'] = fuzz.trapmf(up_time.universe, [0,0,8,16])
up_time['Middle'] = fuzz.trimf(up_time.universe, [8,18,28])
up_time['High'] = fuzz.trapmf(up_time.universe, [20,28,36,36])

#normalized_fault_rate_levels['Under trh'] = fuzz.trapmf(normalized_fault_rate_levels.universe, 1, 0.1)
#normalized_fault_rate_levels['Around trh'] = fuzz.trimf(normalized_fault_rate_levels.universe, [])
#normalized_fault_rate_levels['Above trh'] = fuzz.trapmf(normalized_fault_rate_levels.universe, 3, 0.1)

# Define membership functions for Costlevels
cost_levels['low']=fuzz.trapmf(cost_levels.universe, [0,0,200,500])
cost_levels['medium']=fuzz.trimf(cost_levels.universe, [300,500,700])
cost_levels['high']=fuzz.trapmf(cost_levels.universe, [500,800,1000,1000])

#cost_levels['low']=fuzz.gaussmf(cost_levels.universe, 300,70)
#cost_levels['medium']=fuzz.gaussmf(cost_levels.universe, 500,70)
#cost_levels['high']=fuzz.gaussmf(cost_levels.universe, 700,70)

#Membership madre consequent
reliability['Low']=fuzz.trapmf(reliability.universe, [0,0,2,5])
reliability['Medium']=fuzz.trimf(reliability.universe, [3,5,7])
reliability['High']=fuzz.trapmf(reliability.universe, [5,8,10,10])

mission['Low']=fuzz.trapmf(mission.universe, [0,0,2,5])
mission['Medium']=fuzz.trimf(mission.universe, [3,5,7])
mission['High']=fuzz.trapmf(mission.universe, [5,8,10,10])

# Membershipmadre antecedente 
reliability_result['Low'] = fuzz.trapmf(reliability_result.universe, [0, 0, 2, 5])
reliability_result['Medium'] = fuzz.trimf(reliability_result.universe, [3, 5, 7])
reliability_result['High'] = fuzz.trapmf(reliability_result.universe, [5, 8, 10, 10])

mission_result['Low'] = fuzz.trapmf(mission_result.universe, [0, 0, 2, 5])
mission_result['Medium'] = fuzz.trimf(mission_result.universe, [3, 5, 7])
mission_result['High'] = fuzz.trapmf(mission_result.universe, [5, 8, 10, 10])


# Define membership functions for Criticity
criticity['VeryLow'] = fuzz.gaussmf(criticity.universe, 1, 0.7)
criticity['Low'] = fuzz.gaussmf(criticity.universe, 3, 0.7)
criticity['Medium'] = fuzz.gaussmf(criticity.universe, 5, 0.7)
criticity['High'] = fuzz.gaussmf(criticity.universe, 7, 0.7)
criticity['VeryHigh'] = fuzz.gaussmf(criticity.universe, 9, 0.7)


# Define fuzzy rules

rule_r=[
    #fr high w age
    ctrl.Rule(failure_rate['High'] & normalized_age['New'], reliability['Medium']),
    ctrl.Rule(failure_rate['High'] & normalized_age['Middle'], reliability['Medium']),
    ctrl.Rule(failure_rate['High'] & normalized_age['Old'], reliability['High']),

    #fr medium w age
    ctrl.Rule(failure_rate['Medium'] & normalized_age['New'], reliability['Low']),
    ctrl.Rule(failure_rate['Medium'] & normalized_age['Middle'], reliability['Medium']),
    ctrl.Rule(failure_rate['Medium'] & normalized_age['Old'], reliability['High']),

    #fr low w age
    ctrl.Rule(failure_rate['Low'] & normalized_age['New'], reliability['Low']),
    ctrl.Rule(failure_rate['Low'] & normalized_age['Middle'], reliability['Low']),
    ctrl.Rule(failure_rate['Low'] & normalized_age['Old'], reliability['Medium']),
]

rule_m=[
     # eq function high w uptime
    ctrl.Rule(normalized_fault_rate_levels['Above trh'] & up_time['Low'], mission['Medium']),
    ctrl.Rule(normalized_fault_rate_levels['Above trh'] & up_time['Middle'], mission['High']),
    ctrl.Rule(normalized_fault_rate_levels['Above trh'] & up_time['High'], mission['High']),

    # eq function medium w uptime
    ctrl.Rule(normalized_fault_rate_levels['Around trh'] & up_time['Low'], mission['Low']),
    ctrl.Rule(normalized_fault_rate_levels['Around trh'] & up_time['Middle'], mission['Medium']),
    ctrl.Rule(normalized_fault_rate_levels['Around trh'] & up_time['High'], mission['High']),

    # eq function low w uptime
    ctrl.Rule(normalized_fault_rate_levels['Under trh'] & up_time['Low'], mission['Low']),
    ctrl.Rule(normalized_fault_rate_levels['Under trh'] & up_time['Middle'], mission['Medium']),
    ctrl.Rule(normalized_fault_rate_levels['Under trh'] & up_time['High'], mission['High']),
    
]



rules = [
    #ctrl.Rule(normalized_age['New'], criticity['VeryLow']),
    #ctrl.Rule(normalized_age['Middle'], criticity['Medium']),
    #ctrl.Rule(normalized_age['Old'], criticity['VeryHigh']),

    #ctrl.Rule(normalized_fault_rate_levels['Under trh'], criticity['VeryLow']),
    #ctrl.Rule(normalized_fault_rate_levels['Around trh'], criticity['Medium']),
    #ctrl.Rule(normalized_fault_rate_levels['Above trh'], criticity['VeryHigh']),


    # --- Age: NEW ---
    ctrl.Rule(normalized_age['New'] & normalized_fault_rate_levels['Under trh'], criticity['VeryLow']),
    ctrl.Rule(normalized_age['New'] & normalized_fault_rate_levels['Around trh'], criticity['Low']),
    ctrl.Rule(normalized_age['New'] & normalized_fault_rate_levels['Above trh'], criticity['Medium']),

    # --- Age: MIDDLE ---
    ctrl.Rule(normalized_age['Middle'] & normalized_fault_rate_levels['Under trh'], criticity['Low']),
    ctrl.Rule(normalized_age['Middle'] & normalized_fault_rate_levels['Around trh'], criticity['Medium']),
    ctrl.Rule(normalized_age['Middle'] & normalized_fault_rate_levels['Above trh'], criticity['High']),

    # --- Age: OLD ---
    ctrl.Rule(normalized_age['Old'] & normalized_fault_rate_levels['Under trh'], criticity['Low']),
    ctrl.Rule(normalized_age['Old'] & normalized_fault_rate_levels['Around trh'], criticity['High']),
    ctrl.Rule(normalized_age['Old'] & normalized_fault_rate_levels['Above trh'], criticity['VeryHigh']),

    #cost high w age
    ctrl.Rule(cost_levels['high'] & normalized_age['New'], criticity['Low']),
    ctrl.Rule(cost_levels['high'] & normalized_age['Middle'], criticity['Medium']),
    ctrl.Rule(cost_levels['high'] & normalized_age['Old'], criticity['VeryHigh']),

    #cost medium w age
    ctrl.Rule(cost_levels['medium'] & normalized_age['New'], criticity['VeryLow']),
    ctrl.Rule(cost_levels['medium'] & normalized_age['Middle'], criticity['Medium']),
    ctrl.Rule(cost_levels['medium'] & normalized_age['Old'], criticity['High']),

    #cost low w age
    ctrl.Rule(cost_levels['low'] & normalized_age['New'], criticity['VeryLow']),
    ctrl.Rule(cost_levels['low'] & normalized_age['Middle'], criticity['Low']),
    ctrl.Rule(cost_levels['low'] & normalized_age['Old'], criticity['Medium']),

    # cost high w failure rate
    ctrl.Rule(cost_levels['high'] & normalized_fault_rate_levels['Under trh'], criticity['Low']),
    ctrl.Rule(cost_levels['high'] & normalized_fault_rate_levels['Around trh'], criticity['High']),
    ctrl.Rule(cost_levels['high'] & normalized_fault_rate_levels['Above trh'], criticity['VeryHigh']),

    # cost medium w failure rate
    ctrl.Rule(cost_levels['medium'] & normalized_fault_rate_levels['Under trh'], criticity['VeryLow']),
    ctrl.Rule(cost_levels['medium'] & normalized_fault_rate_levels['Around trh'], criticity['Medium']),
    ctrl.Rule(cost_levels['medium'] & normalized_fault_rate_levels['Above trh'], criticity['High']),

    # cost low w failure rate
    ctrl.Rule(cost_levels['low'] & normalized_fault_rate_levels['Under trh'], criticity['VeryLow']),
    ctrl.Rule(cost_levels['low'] & normalized_fault_rate_levels['Around trh'], criticity['Low']),
    ctrl.Rule(cost_levels['low'] & normalized_fault_rate_levels['Above trh'], criticity['Medium']),


   

]

# Create the control system (this is the equivalent of the fuzzy system in Matlab)
mission_ctrl=ctrl.ControlSystem(rule_m)
reliability_ctrl=ctrl.ControlSystem(rule_r)


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




# Create a simulation object for the fuzzy control system
mission_simulation=ctrl.ControlSystemSimulation(mission_ctrl)
reliability_simulation=ctrl.ControlSystemSimulation(reliability_ctrl)

rule_f = [
    # mission high
    ctrl.Rule(mission_result['High'] & reliability_result['High'], criticity['VeryHigh']),
    ctrl.Rule(mission_result['High'] & reliability_result['Medium'], criticity['High']),
    ctrl.Rule(mission_result['High'] & reliability_result['Low'], criticity['High']),

    # mission medium
    ctrl.Rule(mission_result['Medium'] & reliability_result['High'], criticity['VeryHigh']),
    ctrl.Rule(mission_result['Medium'] & reliability_result['Medium'], criticity['Medium']),
    ctrl.Rule(mission_result['Medium'] & reliability_result['Low'], criticity['Low']),

    # mission low
    ctrl.Rule(mission_result['Low'] & reliability_result['High'], criticity['High']),
    ctrl.Rule(mission_result['Low'] & reliability_result['Medium'], criticity['Low']),
    ctrl.Rule(mission_result['Low'] & reliability_result['Low'], criticity['VeryLow']),
]

    


# Passi dentro gli output già calcolati



# Initialize a list to store the calculated criticities
criticities = []

# Calculate criticity for each device
for nome, val in zip(parametri_nome_prova_con_2_parametri, inputs):
    valore = val if val is not None else 0.0
    
    if nome in ["up_time", "normalized_fault_rate_levels"]:   # parametri per mission
        mission_simulation.input[nome] = valore
    elif nome in ["normalized_age", "failure_rate"]:      # parametri per reliability
        reliability_simulation.input[nome] = valore
# Compute the fuzzy output (Criticity)
def show_fuzzy_output(fuzzy_var, sim):
    # Forzo il calcolo
    sim.compute()
    
    # Normalizzo il nome (per evitare problemi di maiuscole/minuscole)
    var_name = fuzzy_var.label
    output_keys = list(sim.output.keys())

    # Controllo robusto: cerco ignorando le maiuscole
    matching_key = None
    for k in output_keys:
        if k.lower() == var_name.lower():
            matching_key = k
            break

    if matching_key is None:
        raise KeyError(f"Variabile '{var_name}' non trovata tra le uscite disponibili: {output_keys}")

    output_value = sim.output[matching_key]

    # Plot
    fig, ax = plt.subplots(figsize=(5, 2.5))
    colors = plt.cm.viridis(np.linspace(0, 1, len(fuzzy_var.terms)))
    x = fuzzy_var.universe

    for idx, term in enumerate(fuzzy_var.terms):
        mf = fuzzy_var[term].mf
        y = mf

        # Plot della curva
        ax.plot(x, y, label=term.capitalize(), linewidth=1, color=colors[idx])

        # Attivazione
        activation = fuzz.interp_membership(x, y, output_value)
        ax.fill_between(x, 0, np.fmin(activation, y), alpha=0.4, color=colors[idx])

    # Linea sul defuzzificato
    ax.axvline(x=output_value, color='red', linestyle='--', linewidth=1,
               label=f'Uscita = {output_value:.2f}')

    # Stile
    ax.set_title(f"Output fuzzy: {matching_key}", fontsize=9, weight='bold', pad=10)
    ax.set_xlabel("Valore", fontsize=6)
    ax.set_ylabel("Appartenenza", fontsize=6)
    ax.tick_params(labelsize=6)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, fontsize=8, frameon=False)
    fig.tight_layout()

    st.pyplot(fig)
    plt.close(fig)

    return output_value

criticity_ctrl = ctrl.ControlSystem(rule_f)
criticity_simulation = ctrl.ControlSystemSimulation(criticity_ctrl)

reliability_score=show_fuzzy_output(reliability, reliability_simulation)
mission_score=show_fuzzy_output(mission, mission_simulation)

criticity_simulation.input['mission_result'] = mission_score
criticity_simulation.input['reliability_result'] = reliability_score

#criticity_simulation.compute()

#print(criticity_simulation.output['criticity'])
criticity_score=show_fuzzy_output(criticity, criticity_simulation)



# Store the result (scaled by 10 as in your Matlab code)
obsolescenza = criticity_simulation.output['criticity'] * 10


if obsolescenza is not None:
    st.write("**Obsolescence score:**", f"{obsolescenza:.2f}")
    if obsolescenza > 60:
        st.error("⚠️ Device partially obsolet")
    else:
        st.success("✅ Device in good condition")
else:
    st.info("🟡 Inserisci almeno un parametro per calcolare lo score")


def gaussmf(x, mean, sigma):
    return np.exp(-((x - mean) ** 2) / (2 * sigma ** 2))

x_age = np.linspace(0, 1, 100)
young = gaussmf(x_age, 0.2, 0.1)
middle = gaussmf(x_age, 0.5, 0.1)
old = gaussmf(x_age, 0.8, 0.1)

# plot “raw”, adattando il tuo stile
#def plot_raw_membership(x, terms, title):
    #fig, ax = plt.subplots(figsize=(5, 2.5))
    #for name, curve in terms.items():
        #ax.plot(
            #x,
            #curve,
            #label=name.capitalize(),
            #linewidth=1
        #)
    #ax.set_title(title, fontsize=9, weight='bold', pad=10)
    #ax.set_xlabel("Valore", fontsize=6)
    #ax.set_ylabel("Appartenenza", fontsize=6)
    #ax.tick_params(labelsize=6)
    #ax.grid(True, linestyle="--", alpha=0.3)
    #ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25),
    #         ncol=3, fontsize=8, frameon=False)
    #fig.tight_layout()
    #st.pyplot(fig)
    #plt.close(fig)

#plot_raw_membership(
#    x_age,
#    {"young": young, "middle": middle, "old": old},
#    "Age"
#)
plot_membership_functions(normalized_age, 'Age')
plot_membership_functions(normalized_fault_rate_levels, 'Failure rate')
plot_membership_functions(cost_levels, 'Cost')
plot_membership_functions(failure_rate, 'Failure rate')
plot_membership_functions(up_time, 'Uptime')


# --- Salvataggio in Firestore ---
user_email = st.session_state["user"]
if st.button("Save valuation"):
    parametri_dict = {
    nome: val if val is not None else None
    for nome, val in zip(parametri_nome_prova_con_2_parametri, inputs)
    }

    doc = {
        "parametri": parametri_dict,
        "obsolescenza": float(f"{obsolescenza:.2f}") if obsolescenza is not None else None
    }
    
 
    db.collection("ospedali").document(user_email).collection("valutazioni").add(doc)
    st.success("✅ Valutation saved!")

st.subheader("📋 Valutations saved")
valutazioni = db.collection("ospedali").document(user_email).collection("valutazioni").stream()

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def calcola_obsolescenza(row):
    """
    Funzione per calcolare l'obsolescenza basata sui parametri.
    Modifica questa funzione con la tua logica di calcolo.
    """
    # Esempio di calcolo - sostituisci con la tua formula
    param_cols = [col for col in row.index if col.startswith('param_') or col not in ['Obsolescence']]
    if len(param_cols) == 0:
        return 0.0
    
    # Esempio: media dei parametri (sostituisci con la tua formula)
    values = [safe_float(row[col]) for col in param_cols]
    media = sum(values) / len(values) if values else 0.0
    
    # Esempio di formula per obsolescenza (modifica secondo le tue esigenze)
    obsolescenza = min(100, max(0, media * 10))  # scala da 0 a 100
    
    return round(obsolescenza, 2)

# Costruiamo la lista di dizionari dai tuoi dati
rows = []
for doc in valutazioni:
    d = doc.to_dict()
    params = d.get("parametri", ["N/D"]*13)
    score = d.get("obsolescenza", "N/D")
    if isinstance(params, dict):
        row = {k: safe_float(v) for k, v in params.items()}
    else:
        row = {f"param_{i+1}": safe_float(v) for i, v in enumerate(params)}
    # Calcola l'obsolescenza iniziale
    row["Obsolescence"] = safe_float(score)
    rows.append(row)

# Creiamo il DataFrame
df_original = pd.DataFrame(rows)

# Salviamo una copia per confronti
if 'previous_df' not in st.session_state:
    st.session_state.previous_df = df_original.copy()

# Configuriamo AgGrid per essere editabile
gb = GridOptionsBuilder.from_dataframe(df_original)

# Configurazione generale
gb.configure_default_column(
    editable=True, 
    resizable=True, 
    sortable=True,
    filter=True,
    floatingFilter=False
)

# Configura colonne dei parametri (editabili)
param_cols = [col for col in df_original.columns if col != 'Obsolescence']
for col in param_cols:
    gb.configure_column(
        col, 
        editable=True,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        precision=2,
        cellStyle={'backgroundColor': '#ffffff'}
    )

# La colonna Obsolescence non modificabile ma evidenziata
gb.configure_column(
    "Obsolescence", 
    editable=False,
    cellStyle={'backgroundColor': '#e8f4f8', 'fontWeight': 'bold'},
    type=["numericColumn"],
    precision=2
)

# Configurazioni aggiuntive per l'editing
gb.configure_grid_options(
    enableRangeSelection=True,
    enableClipboard=True,
    suppressMovableColumns=False
)

# Costruisci le opzioni
grid_options = gb.build()

# Visualizza la tabella interattiva
st.write("### Valutazioni (Doppio click per modificare - Obsolescence si ricalcola automaticamente)")

grid_response = AgGrid(
    st.session_state.previous_df,
    gridOptions=grid_options,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    fit_columns_on_grid_load=True,
    enable_enterprise_modules=False,
    allow_unsafe_jscode=True,
    height=400,
    width='100%',
    reload_data=True,
    key='aggrid_table'  # Chiave unica per la tabella
)

# Recupera il DataFrame modificato
df_edited = grid_response['data']

# Controlla se ci sono state modifiche nei parametri
changes_detected = False
df_with_recalc = df_edited.copy()

# Ricalcola l'obsolescenza per ogni riga se i parametri sono cambiati
for idx in df_edited.index:
    old_params = st.session_state.previous_df.loc[idx, param_cols] if idx < len(st.session_state.previous_df) else None
    new_params = df_edited.loc[idx, param_cols]
    
    # Controlla se i parametri sono cambiati
    if old_params is None or not old_params.equals(new_params):
        changes_detected = True
        # Ricalcola l'obsolescenza
        new_obsolescence = calcola_obsolescenza(df_edited.loc[idx])
        df_with_recalc.loc[idx, 'Obsolescence'] = new_obsolescence

# Se ci sono state modifiche, aggiorna la session state e ricarica
if changes_detected:
    st.session_state.previous_df = df_with_recalc.copy()
    st.rerun()

# Mostra le informazioni sulle modifiche
if not df_original.equals(df_with_recalc):
    st.write("### ✅ Dati modificati (Obsolescence ricalcolata)")
    
    # Mostra le modifiche in dettaglio
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Valori originali:**")
        st.dataframe(df_original, use_container_width=True)
    
    with col2:
        st.write("**Valori modificati:**")
        st.dataframe(df_with_recalc, use_container_width=True)
    
    # Pulsante per salvare
    if st.button("💾 Salva modifiche nel database", type="primary"):
        # Qui salvi le modifiche nel database
        for idx, row in df_with_recalc.iterrows():
            # Esempio di salvataggio (adatta al tuo database)
            # doc_ref = valutazioni[idx]  # riferimento al documento
            # doc_ref.update({
            #     'parametri': row[param_cols].to_dict(),
            #     'obsolescenza': row['Obsolescence']
            # })
            pass
        
        st.success("✅ Modifiche salvate nel database!")
        st.balloons()
    
    # Reset button
    if st.button("🔄 Reset alle condizioni originali"):
        st.session_state.previous_df = df_original.copy()
        st.rerun()

else:
    st.write("### ℹ️ Nessuna modifica effettuata")

# Istruzioni per l'utente
with st.expander("📖 Come utilizzare la tabella"):
    st.write("""
    1. **Modifica parametri**: Fai doppio click su una cella dei parametri e inserisci il nuovo valore
    2. **Conferma**: Premi Enter o clicca fuori dalla cella
    3. **Ricalcolo automatico**: L'obsolescenza viene ricalcolata automaticamente
    4. **Salva**: Clicca il pulsante "Salva modifiche" per confermare nel database
    5. **Reset**: Usa il pulsante "Reset" per tornare ai valori originali
    """)

# Sezione per personalizzare la formula di calcolo
with st.expander("⚙️ Personalizza formula obsolescenza"):
    st.write("""
    **Formula attuale**: Media dei parametri × 10 (limitata tra 0 e 100)
    
    Per modificare la formula, cambia la funzione `calcola_obsolescenza()` nel codice:
    
    ```python
    def calcola_obsolescenza(row):
        # La tua formula personalizzata qui
        # Esempio: return sum(values) / len(values) * fattore_scala
    ```
    """)




#ctrl.Rule(normalized_eols['Absent'], criticity['VeryLow']),
#ctrl.Rule(normalized_eols['PresentEoLBeforeToday'], criticity['High']),
#ctrl.Rule(normalized_eols['PresentEoSAfterToday'], criticity['High']),
#ctrl.Rule(normalized_eols['PresentEoSBeforeToday'], criticity['VeryHigh'])

#ctrl.Rule(normalized_risk_levels['NotSignificant'], criticity['VeryLow']),
#ctrl.Rule(normalized_risk_levels['NonPermanent'], criticity['Low']),
#ctrl.Rule(normalized_risk_levels['ErrataTherapy'], criticity['Medium']),
#ctrl.Rule(normalized_risk_levels['Permanent'], criticity['High']),
#ctrl.Rule(normalized_risk_levels['Death'], criticity['VeryHigh']),

#ctrl.Rule(normalized_function_levels['LowIntensity'], criticity['VeryLow']),
#ctrl.Rule(normalized_function_levels['MidLowIntensity'], criticity['Low']),
#ctrl.Rule(normalized_function_levels['MidIntensity'], criticity['Medium']),
#ctrl.Rule(normalized_function_levels['MidHighIntensity'], criticity['High']),
#ctrl.Rule(normalized_function_levels['HighIntensity'], criticity['VeryHigh']),
#ctrl.Rule(normalized_function_levels['VeryHighIntensity'], criticity['VeryHigh']),

#ctrl.Rule(normalized_state_levels['Buono'], criticity['VeryLow']),
#ctrl.Rule(normalized_state_levels['Sufficiente'], criticity['Medium']),
#ctrl.Rule(normalized_state_levels['Deteriorato'], criticity['High']),
#ctrl.Rule(normalized_state_levels['Degradato'], criticity['VeryHigh']),

#ctrl.Rule(normalized_life_res_levels['BrandNew'], criticity['VeryLow']),
#ctrl.Rule(normalized_life_res_levels['Recent'], criticity['Low']),
#ctrl.Rule(normalized_life_res_levels['FairlyNew'], criticity['Medium']),
#ctrl.Rule(normalized_life_res_levels['UsedButGoodCondition'], criticity['High']),

#ctrl.Rule(normalized_utilization_levels['Stock'], criticity['VeryLow']),
#ctrl.Rule(normalized_utilization_levels['Unused'], criticity['Low']),
#ctrl.Rule(normalized_utilization_levels['RarelyUsed'], criticity['Medium']),
#ctrl.Rule(normalized_utilization_levels['ContinuousUse'], criticity['High']),

#ctrl.Rule(normalized_obs_levels['StateOfTheArt'], criticity['VeryLow']),
#ctrl.Rule(normalized_obs_levels['UsableWithRemainingLifeLessThan0'], criticity['Low']),
#ctrl.Rule(normalized_obs_levels['UsableWithRemainingLifeGreaterOrEqual0'], criticity['Medium']),
#ctrl.Rule(normalized_obs_levels['Obsolete'], criticity['High']),

#ctrl.Rule(normalized_uptime['Min'], criticity['VeryHigh']),
#ctrl.Rule(normalized_uptime['Middle'], criticity['Medium']),
#ctrl.Rule(normalized_uptime['Max'], criticity['VeryLow']),

#normalized_risk_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedRiskLevels')
#normalized_function_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedfunctionLevels')
#normalized_state_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedStateLevels')
#normalized_life_res_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedLifeResLevels')
#normalized_obs_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedObsLevels')
#normalized_utilization_levels = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedUtilizationLevels')
#normalized_uptime = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedUptime')
#normalized_eols = ctrl.Antecedent(np.arange(0, 1.1, 0.1), 'normalizedEoLS')

# Define membership functions for normalizedEoLS
#normalized_eols['Absent'] = fuzz.trimf(normalized_eols.universe, [0, 0, 0.125])
#normalized_eols['PresentEoLBeforeToday'] = fuzz.trapmf(normalized_eols.universe, [0.25, 0.375, 0.625, 0.75])
#normalized_eols['PresentEoSAfterToday'] = fuzz.trapmf(normalized_eols.universe, [0.5, 0.625, 0.875, 1])
#normalized_eols['PresentEoSBeforeToday'] = fuzz.trimf(normalized_eols.universe, [0.75, 0.875, 1])

# Define membership functions for normalizedRiskLevels
#normalized_risk_levels['NotSignificant'] = fuzz.trapmf(normalized_risk_levels.universe, [0, 0, 0.1, 0.2])
#normalized_risk_levels['NonPermanent'] = fuzz.trimf(normalized_risk_levels.universe, [0.15, 0.2, 0.25])
#normalized_risk_levels['ErrataTherapy'] = fuzz.trimf(normalized_risk_levels.universe, [0.25, 0.35, 0.45])
#normalized_risk_levels['Permanent'] = fuzz.trapmf(normalized_risk_levels.universe, [0.45, 0.55, 0.65, 0.75])
#normalized_risk_levels['Death'] = fuzz.trapmf(normalized_risk_levels.universe, [0.75, 0.80, 0.90, 1])

# Define membership functions for normalizedfunctionLevels
#normalized_function_levels['LowIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0, 0, 0.1, 0.2])
#normalized_function_levels['MidLowIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.15, 0.2, 0.25])
#normalized_function_levels['MidIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.25, 0.35, 0.45])
#normalized_function_levels['MidHighIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0.45, 0.55, 0.65, 0.75])
#normalized_function_levels['HighIntensity'] = fuzz.trimf(normalized_function_levels.universe, [0.7, 0.8, 0.9])
#normalized_function_levels['VeryHighIntensity'] = fuzz.trapmf(normalized_function_levels.universe, [0.85, 1, 1, 1])

# Define membership functions for normalizedStateLevels
#normalized_state_levels['Buono'] = fuzz.trapmf(normalized_state_levels.universe, [0, 0, 0.1, 0.2])
#normalized_state_levels['Sufficiente'] = fuzz.trimf(normalized_state_levels.universe, [0.15, 0.2, 0.25])
#normalized_state_levels['Deteriorato'] = fuzz.trimf(normalized_state_levels.universe, [0.25, 0.35, 0.45])
#normalized_state_levels['Degradato'] = fuzz.trapmf(normalized_state_levels.universe, [0.45, 0.55, 0.75, 1])

# Define membership functions for normalizedLifeResLevels
#normalized_life_res_levels['BrandNew'] = fuzz.trimf(normalized_life_res_levels.universe, [0, 0, 0.2])
#normalized_life_res_levels['Recent'] = fuzz.trimf(normalized_life_res_levels.universe, [0.15, 0.3, 0.45])
#normalized_life_res_levels['FairlyNew'] = fuzz.trimf(normalized_life_res_levels.universe, [0.4, 0.55, 0.7])
#normalized_life_res_levels['UsedButGoodCondition'] = fuzz.trimf(normalized_life_res_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedUtilizationLevels
#normalized_utilization_levels['Stock'] = fuzz.trimf(normalized_utilization_levels.universe, [0, 0, 0.2])
#normalized_utilization_levels['Unused'] = fuzz.trimf(normalized_utilization_levels.universe, [0.15, 0.3, 0.45])
#normalized_utilization_levels['RarelyUsed'] = fuzz.trimf(normalized_utilization_levels.universe, [0.4, 0.55, 0.7])
#normalized_utilization_levels['ContinuousUse'] = fuzz.trimf(normalized_utilization_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedObsLevels
#normalized_obs_levels['StateOfTheArt'] = fuzz.trimf(normalized_obs_levels.universe, [0, 0, 0.2])
#normalized_obs_levels['UsableWithRemainingLifeLessThan0'] = fuzz.trimf(normalized_obs_levels.universe, [0.15, 0.3, 0.45])
#normalized_obs_levels['UsableWithRemainingLifeGreaterOrEqual0'] = fuzz.trimf(normalized_obs_levels.universe, [0.4, 0.55, 0.7])
#normalized_obs_levels['Obsolete'] = fuzz.trimf(normalized_obs_levels.universe, [0.6, 0.8, 1])

# Define membership functions for normalizedUptime

#normalized_uptime['Max'] = fuzz.trapmf(normalized_uptime.universe, [0.6, 0.8, 1, 1])
#normalized_uptime['Middle'] = fuzz.trimf(normalized_uptime.universe, [0.3, 0.5, 0.7])
#normalized_uptime['Min'] = fuzz.trapmf(normalized_uptime.universe, [0, 0, 0.2, 0.4])





