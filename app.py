
import streamlit as st
import numpy as np
import skfuzzy as fuzz

st.title("Valutazione Obsolescenza Dispositivo Medico")

# Input utente
eta = st.slider("Età del dispositivo (anni)", 0, 30, 10)
utilizzo = st.slider("Ore di utilizzo annuali", 0, 5000, 1000)

# Definisci universo e funzioni di appartenenza
eta_range = np.arange(0, 31, 1)
uso_range = np.arange(0, 5001, 100)

# Membership per età
giovane = fuzz.trimf(eta_range, [0, 0, 15])
vecchio = fuzz.trimf(eta_range, [10, 30, 30])

# Membership per utilizzo
basso = fuzz.trimf(uso_range, [0, 0, 2000])
alto = fuzz.trimf(uso_range, [1000, 5000, 5000])

# Fuzzificazione input
eta_g = fuzz.interp_membership(eta_range, giovane, eta)
eta_v = fuzz.interp_membership(eta_range, vecchio, eta)
uso_b = fuzz.interp_membership(uso_range, basso, utilizzo)
uso_a = fuzz.interp_membership(uso_range, alto, utilizzo)

# Regola fuzzy semplice
obsolescenza = max(eta_v, uso_a)

# Output
st.write("**Grado di obsolescenza:**", f"{obsolescenza:.2f}")
if obsolescenza > 0.6:
    st.error("⚠️ Dispositivo potenzialmente obsoleto")
else:
    st.success("✅ Dispositivo in buone condizioni")
