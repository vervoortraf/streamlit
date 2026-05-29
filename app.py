import streamlit as st
import requests
import json
import tempfile
import os
import math
import gerbonara
from sklearn.cluster import DBSCAN
import numpy as np

# --- CONFIGURATIE ---
# Pas dit aan naar de Test-URL van jouw n8n Webhook
N8N_WEBHOOK_URL = "https://jouw-n8n-instantie.n8n.cloud/webhook-test/component-recognition"

st.set_page_config(page_title="AI Gerber Analist (Live Data)", layout="wide")
st.title("Stap 2: Analyse met Échte Gerber Data")

st.info("Upload je Top Copper (.gbr). Python clustert de pads en Claude herkent de componenten.")

top_copper = st.file_uploader("Upload Top Copper Gerber (.gbr)", type=['gbr', 'pho', 'art'])

# --- HELPER FUNCTIES ---
def analyze_real_gerber(gerber_bytes):
    """
    Leest de echte Gerber in, haalt alle flitsen (pads) op en clustert ze met DBSCAN.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gbr") as tmp:
        tmp.write(gerber_bytes)
        tmp_path = tmp.name

    try:
        # Lees het bestand in
        layer = gerbonara.rs274x.GerberFile.open(tmp_path)
        
        pads = []
        # Zoek alle pads, maar zonder de breekbare import. We checken gewoon de class-naam!
        for obj in layer.objects:
            if type(obj).__name__ == 'Flash':
                pads.append([obj.x, obj.y])

        if not pads:
            return {"error": "Geen pads (Flashes) gevonden in deze Gerber. Zorg dat het de Paste- of Copperlaag is."}

        pads_array = np.array(pads)

        # Clustering: groepeer pads die < 0.8mm van elkaar liggen
        clustering = DBSCAN(eps=0.8, min_samples=2).fit(pads_array)
        labels = clustering.labels_

        clusters_data = []
        for cluster_id in set(labels):
            if cluster_id == -1:
                continue # Negeer "ruis" (losse pads zonder buren)
                
            cluster_points = pads_array[labels == cluster_id]
            pad_count = len(cluster_points)
            
            x_min, y_min = np.min(cluster_points, axis=0)
            x_max, y_max = np.max(cluster_points, axis=0)
            
            pitch_estimate = 0
            if pad_count >= 2:
                dx = cluster_points[1][0] - cluster_points[0][0]
                dy = cluster_points[1][1] - cluster_points[0][1]
                pitch_estimate = round(math.sqrt(dx**2 + dy**2), 3)

            clusters_data.append({
                "cluster_id": f"Comp_{cluster_id}",
                "pad_count": pad_count,
                "estimated_pitch_mm": pitch_estimate,
                "bounding_box": {
                    "x_min": round(float(x_min), 3),
                    "y_min": round(float(y_min), 3),
                    "x_max": round(float(x_max), 3),
                    "y_max": round(float(y_max), 3)
                }
            })
            
            # Beperk tot max 50 componenten om te voorkomen dat we de API overbelasten
            if len(clusters_data) >= 50:
                break

        os.remove(tmp_path)
        return {"clusters": clusters_data}

    except Exception as e:
        if os.path.exists(tmp_path): os.remove(tmp_path)
        return {"error": str(e)}

def write_raw_gerber_boxes(recognized_data, output_filename="ai_component_kaders.gbr"):
    """
    Schrijft direct hard-coded RS-274X Gerber uit. Geen libraries nodig.
    """
    def fmt(val): return str(int(round(float(val) * 100000)))

    lines = [
        "%FSLAX45Y45*%", "%MOMM*%", "%LPD*%", 
        "%ADD10C,0.1000*%", "D10*", "G01*",
        f"X{fmt(0)}Y{fmt(0)}D02*", f"X{fmt(0.5)}Y{fmt(0.5)}D01*" 
    ]
    
    components = recognized_data.get("recognized_components", [])
    for comp in components:
        box = comp.get("bounding_box")
        if not box: continue
        x_min, y_min = float(box.get("x_min", 0.0)), float(box.get("y_min", 0.0))
        x_max, y_max = float(box.get("x_max", 0.0)), float(box.get("y_max", 0.0))
        
        # Trek het vierkant met een kleine offset (0.2mm) zodat het originele koper er mooi binnen valt
        x_min, y_min = x_min - 0.2, y_min - 0.2
        x_max, y_max = x_max + 0.2, y_max + 0.2
        
        lines.append(f"X{fmt(x_min)}Y{fmt(y_min)}D02*")
        lines.append(f"X{fmt(x_max)}Y{fmt(y_
