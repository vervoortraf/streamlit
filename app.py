import streamlit as st
import requests
import json
import gerbonara
from gerbonara.cad.primitives import Line
from gerbonara.apertures import CircleAperture

# --- JOUW N8N WEBHOOK URL ---
# Pas dit aan naar de Test-URL van jouw n8n Webhook
N8N_WEBHOOK_URL = "https://ravoortt.app.n8n.cloud/webhook-test/ff70e4f4-afb8-4faa-91b9-bb4046bdc2c9"

st.set_page_config(page_title="AI Gerber Component Herkenning", layout="wide")
st.title("Stap 1: Component Herkenning & Gerber Kader Generatie")

st.info("Upload de Copper en Solder Mask lagen. De AI zal proberen componenten te herkennen en genereert een nieuwe Gerber-laag met kaders en tekst.")

col1, col2 = st.columns(2)

with col1:
    top_copper = st.file_uploader("Top Copper (.gbr)", type=['gbr', 'pho'])
    solder_mask = st.file_uploader("Top Solder Mask (.gbr)", type=['gbr', 'pho'])

def extract_spatial_data(copper_file):
    """
    In productie groepeer je hier de echte pads. 
    Voor deze test simuleren we het ruimtelijke overzicht dat je naar n8n stuurt.
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

def draw_bounding_box_gerber(recognized_data, output_filename="ai_component_kaders.gbr"):
    """
    Maakt een compleet nieuwe Gerber layer en tekent vierkanten (bounding boxes) 
    op basis van de output van de n8n AI Agent.
    """
    # Maak een nieuw, leeg Gerber bestand aan (standaard in mm)
    layer = gerbonara.rs274x.GerberFile()
    
    # We definiëren de kwast (aperture): een ronde lijn van 0.1mm dik
    aperture = CircleAperture(0.1, unit='mm')

    # Haal de lijst met componenten uit de JSON
    components = recognized_data.get("recognized_components", [])

    for comp in components:
        box = comp.get("bounding_box", {})
        if not box:
            continue
            
        x_min = float(box.get("x_min", 0.0))
        y_min = float(box.get("y_min", 0.0))
        x_max = float(box.get("x_max", 0.0))
        y_max = float(box.get("y_max", 0.0))
        
        # Trek de 4 lijnen van het vierkant en wijs direct de aperture toe
        layer.objects.append(Line(x_min, y_min, x_max, y_min, aperture=aperture)) # Onderkant
        layer.objects.append(Line(x_max, y_min, x_max, y_max, aperture=aperture)) # Rechterkant
        layer.objects.append(Line(x_max, y_max, x_min, y_max, aperture=aperture)) # Bovenkant
        layer.objects.append(Line(x_min, y_max, x_min, y_min, aperture=aperture)) # Linkerkant
        
    # Bestand opslaan
    layer.save(output_filename)
    return output_filename

# --- ACTIE ---
if st.button("Start Component Herkenning", type="primary"):
    if not top_copper:
        st.warning("Upload aub een dummy bestand (mag elk .gbr bestand zijn) om de trigger te starten.")
    else:
        with st.spinner("Ruimtelijke map wordt opgebouwd en naar Claude (n8n) gestuurd..."):
            
            # 1. Haal de context op
            spatial_data = extract_spatial_data(top_copper)
            
            # 2. Maak de payload voor n8n
            payload = {"pcb_spatial_data": spatial_data}
            headers = {'Content-Type': 'application/json'}
            
            try:
                # 3. Verstuur naar n8n
                response = requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
                
                if response.status_code == 200:
                    ai_result = response.json()
                    st.success("✅ AI heeft de componenten geanalyseerd!")
                    
                    # Toon het JSON resultaat op het scherm
                    st.json(ai_result)
                    
                    # 4. Teken de nieuwe Gerber laag
                    output_file = draw_bounding_box_gerber(ai_result)
                    
                    # 5. Maak de download knop aan
                    with open(output_file, "rb") as file:
                        st.download_button(
                            label="📥 Download AI Kaders Gerber (.gbr)",
                            data=file,
                            file_name="ai_component_kaders.gbr",
                            mime="application/octet-stream"
                        )
                        st.info("Tip: Laad deze Gerber in je CAM software (bijv. GC-Prevue of GerbView) over je originele koperlaag heen om de kaders visueel te controleren.")
                        
                else:
                    st.error(f"Fout vanuit n8n (HTTP {response.status_code}): {response.text}")
                    
            except Exception as e:
                st.error(f"Er ging iets mis met de verbinding naar n8n: {e}")
