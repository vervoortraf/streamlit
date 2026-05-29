import streamlit as st
import requests
import json

# --- JOUW N8N WEBHOOK URL ---
# Kopieer de 'Test URL' uit je n8n Webhook node.
N8N_WEBHOOK_URL = "https://ravoortt.app.n8n.cloud/webhook-test/ff70e4f4-afb8-4faa-91b9-bb4046bdc2c9"

st.set_page_config(page_title="AI Stencil Ontwerper", layout="wide")
st.title("ROTEC AI Stencil Tool")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Upload Bestanden")
    # In deze basisfase gebruiken we dummy data, later koppelen we echte Gerbers
    st.info("Voor deze testfase sturen we gesimuleerde pad-data.")
    basis_dikte = st.number_input("Standaard stencildikte (micron)", value=120)

with col2:
    st.subheader("2. DFM Regels")
    klant_regels = st.text_area("Typ hier de specifieke regels", 
                                value="BGA met pitch < 0.5mm: pas 55% reductie toe en ontwerp een step-down naar 100 micron als de Area Ratio te laag wordt.")

if st.button("Start AI Ontwerp", type="primary"):
    with st.spinner("Data wordt naar n8n en Claude gestuurd..."):
        
        # Dit is de dummy-data die we simuleren alsof het uit een Gerber komt
        dummy_pcb_data = {
            "dikte_micron": basis_dikte,
            "ruwe_pads": [
                {"id": "pad_groep_1", "vorm": "rond", "aantal": 36, "afstand_onderling_mm": 0.4},
                {"id": "pad_groep_2", "vorm": "rechthoek", "aantal": 12, "afstand_onderling_mm": 1.2}
            ]
        }
        
        payload = {
            "pcb_data": dummy_pcb_data,
            "rules": klant_regels
        }
        
        headers = {'Content-Type': 'application/json'}
        
        try:
            # We sturen de data naar n8n
            response = requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
            
            if response.status_code == 200:
                st.success("✅ Workflow succesvol gestart!")
                # Laat het antwoord van n8n zien
                st.json(response.json())
            else:
                st.error(f"Er ging iets mis: HTTP {response.status_code}")
                
        except Exception as e:
            st.error(f"Kan n8n niet bereiken. Controleer de URL. Fout: {e}")
