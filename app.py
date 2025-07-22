import streamlit as st
import numpy as np
import skfuzzy as fuzz
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Inizializza Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(st.secrets["firebase"])
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.title("📟 Valutazione Obsolescenza Dispositivo Medico")

st.header("➕ Inserisci nuovo dispositivo")

with st.form("form_dispositivo"):
    nome = st.text_input("Nome del dispositivo")
    marca = st.text_input("Marca")
    eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
    utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)
    submitted = st.form_submit_button("Valuta e Salva")

    if submitted:
        # Definizione degli universi fuzzy
        eta_range = np.arange(0, 31, 1)
        uso_range = np.arange(0, 5001, 100)

        # Funzioni di membership
        giovane = fuzz.trimf(eta_range, [0, 0, 15])
        vecchio = fuzz.trimf(eta_range, [10, 30, 30])
        basso = fuzz.trimf(uso_range, [0, 0, 2000])
        alto = fuzz.trimf(uso_range, [1000, 5000, 5000])

        # Fuzzificazione input
        eta_g = fuzz.interp_membership(eta_range, giovane, eta)
        eta_v = fuzz.interp_membership(eta_range, vecchio, eta)
        uso_b = fuzz.interp_membership(uso_range, basso, utilizzo)
        uso_a = fuzz.interp_membership(uso_range, alto, utilizzo)

        # Regola fuzzy (puoi espandere con più regole)
        obsolescenza = max(eta_v, uso_a)

        # Valutazione
        stato = "Obsoleto" if obsolescenza > 0.6 else "Funzionante"

        # Mostra risultato
        st.write("**Grado di obsolescenza:**", f"{obsolescenza:.2f}")
        if stato == "Obsoleto":
            st.error("⚠️ Dispositivo potenzialmente obsoleto")
        else:
            st.success("✅ Dispositivo in buone condizioni")

        # Salva su Firebase
        db.collection("dispositivi").add({
            "nome": nome,
            "marca": marca,
            "eta": eta,
            "utilizzo": utilizzo,
            "obsolescenza": round(obsolescenza, 2),
            "stato": stato,
            "inserito_il": datetime.now()
        })

        st.success("📥 Dati salvati nel database!")

st.divider()
st.header("📋 Elenco dispositivi salvati")

# Mostra i dati salvati
dispositivi = db.collection("dispositivi").order_by("inserito_il", direction=firestore.Query.DESCENDING).stream()

dati = []
for d in dispositivi:
    dati.append(d.to_dict())

if dati:
    st.dataframe(dati)
else:
    st.info("Nessun dispositivo ancora salvato.")
