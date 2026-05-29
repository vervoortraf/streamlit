import streamlit as st
import requests
import json

# --- JOUW N8N WEBHOOK URL ---
# Pas dit aan naar de Test-URL van jouw n8n Webhook
N8N_WEBHOOK_URL = "https://ravoortt.app.n8n.cloud/webhook-test/ff70e4f4-afb8-4faa-91b9-bb4046bdc2c9"

st.set_page_config(page_title="AI Gerber Component Herkenning", layout="wide")
st.title("Stap 1: Component Herkenning & Gerber Kader Generatie")

st.info("Upload de Copper en Solder Mask lagen. De AI zal proberen componenten te herkennen en genereert een nieuwe Gerber-laag met kaders.")

col1, col2 = st.columns(2)

with col1:
    top_copper = st.file_uploader("Top Copper (.gbr)", type=['gbr', 'pho'])
    solder_mask = st.file_uploader("Top Solder Mask (.gbr)", type=['gbr', 'pho'])

def extract_spatial_data(copper_file):
    """
    Dit is de ruimtelijke dummy-data (een BGA en een kleine chip).
    Hiermee controleren we of n8n en de AI werken.
    """
    spatial_map = {
        "clusters": [
            {
                "cluster_id": "C1",
                "description": "Matrix van 4x4 ronde pads, diameter 0.25mm",
                "pads": [
                    {"x": 10.0, "y": 10.0}, {"x": 10.4, "y": 10.0}, {"x": 10.8, "y": 10.0}, {"x": 11.2, "y": 10.0},
                    {"x": 10.0, "y": 10.4}, {"x": 10.4, "y": 10.4}, {"x": 10.8, "y": 10.4}, {"x": 11.2, "y": 10.4}
                ]
            },
            {
                "cluster_id": "C2",
                "description": "Twee rechthoekige pads van 0.6x0.7mm, afstand tussen centers is 1.0mm",
                "pads": [
                    {"x": 20.0, "y": 15.0}, {"x": 21.0, "y": 15.0}
                ]
            }
        ]
    }
    return spatial_map

def write_raw_gerber_boxes(recognized_data, output_filename="ai_component_kaders.gbr"):
    """
    Schrijft direct hard-coded RS-274X Gerber uit. Geen libraries nodig.
    100% garantie dat dit leesbaar is in GC-Prevue of andere CAM software.
    """
    def fmt(val):
        # Converteer millimeter naar het 4.5 integer formaat (x 100.000)
        return str(int(round(float(val) * 100000)))

    lines = [
        "%FSLAX45Y45*%",      # Formaat: Leading zeros omitted, Absolute, 4.5 mm
        "%MOMM*%",            # Instellen op Millimeters
        "%LPD*%",             # Layer Polarity Dark
        "%ADD10C,0.1000*%",   # Definieer D10 als Cirkel van 0.1mm
        "D10*",               # Selecteer gereedschap D10
        "G01*"                # Zet in lineaire tekenmodus
    ]
    
    # 1. Teken een klein referentie-kruisje op 0,0 
    # (Als de file 'leeg' lijkt, zoek dan naar X=0 Y=0 in je CAM software!)
    lines.append(f"X{fmt(0)}Y{fmt(0)}D02*")
    lines.append(f"X{fmt(0.5)}Y{fmt(0.5)}D01*")
    
    # 2. Haal de AI componenten op
    components = recognized_data.get("recognized_components", [])
    
    if not components:
        st.warning("Let op: De AI JSON bevatte geen 'recognized_components'. Enkel het referentie-kruisje is getekend.")

    for comp in components:
        box = comp.get("bounding_box")
        if not box:
            continue
            
        x_min, y_min = float(box.get("x_min", 0.0)), float(box.get("y_min", 0.0))
        x_max, y_max = float(box.get("x_max", 0.0)), float(box.get("y_max", 0.0))
        
        # Teken het vierkant: D02 is 'Move' (Pen omhoog), D01 is 'Draw' (Pen omlaag)
        lines.append(f"X{fmt(x_min)}Y{fmt(y_min)}D02*")
        lines.append(f"X{fmt(x_max)}Y{fmt(y_min)}D01*")
        lines.append(f"X{fmt(x_max)}Y{fmt(y_max)}D01*")
        lines.append(f"X{fmt(x_min)}Y{fmt(y_max)}D01*")
        lines.append(f"X{fmt(x_min)}Y{fmt(y_min)}D01*")
        
    lines.append("M02*") # Einde van de file
    
    with open(output_filename, "w") as f:
        f.write("\n".join(lines) + "\n")
        
    return output_filename

# --- ACTIE ---
if st.button("Start Component Herkenning", type="primary"):
    if not top_copper:
        st.warning("Upload aub een willekeurig dummy bestand om de workflow te starten.")
    else:
        with st.spinner("Data wordt naar n8n gestuurd..."):
            
            spatial_data = extract_spatial_data(top_copper)
            payload = {"pcb_spatial_data": spatial_data}
            headers = {'Content-Type': 'application/json'}
            
            try:
                response = requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
                
                if response.status_code == 200:
                    n8n_data = response.json()
                    
                    # --- DE ANTI-MARKDOWN FIX ---
                    # Haal de ruwe tekst op uit n8n (waar de markdown nog in zit)
                    raw_text = n8n_data.get("output", "")
                    
                    # Snij de ```json en ``` weg als de AI eigenwijs was
                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                        
                    # Zet de schone tekst om naar een échte JSON/Dictionary
                    ai_result = json.loads(raw_text)
                    # -----------------------------
                    
                    st.success("✅ Workflow geslaagd! Markdown netjes weggepoetst.")
                    
                    st.json(ai_result)
                    
                    # Genereer de robuuste gerber
                    output_file = write_raw_gerber_boxes(ai_result)
                    
                    with open(output_file, "rb") as file:
                        st.download_button(
                            label="📥 Download AI Kaders Gerber (.gbr)",
                            data=file,
                            file_name="ai_component_kaders.gbr",
                            mime="application/octet-stream"
                        )
                        st.info("Laad deze Gerber in je CAM software. Je zou nu de kaders op X:10 en X:20 moeten zien!")
                        
                else:
                    st.error(f"Fout vanuit n8n (HTTP {response.status_code}): {response.text}")
                    
            except Exception as e:
                st.error(f"Er ging iets mis met de verbinding naar n8n: {e}")
