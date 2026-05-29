import streamlit as st
import requests
import json
import gerbonara
from gerbonara.cad.primitives import Line
from gerbonara.apertures import CircleAperture

# --- JOUW N8N WEBHOOK URL ---
# Pas dit aan naar de Test-URL van jouw n8n Webhook
N8N_WEBHOOK_URL = "https://jouw-n8n-instantie.n8n.cloud/webhook-test/component-recognition"

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
    if not
