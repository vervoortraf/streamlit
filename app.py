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
        lines.append(f"X{fmt(x_max)}Y{fmt(y_min)}D01*")
        lines.append(f"X{fmt(x_max)}Y{fmt(y_max)}D01*")
        lines.append(f"X{fmt(x_min)}Y{fmt(y_max)}D01*")
        lines.append(f"X{fmt(x_min)}Y{fmt(y_min)}D01*")
        
    lines.append("M02*")
    with open(output_filename, "w") as f:
        f.write("\n".join(lines) + "\n")
    return output_filename

# --- ACTIE ---
if st.button("Start AI Analyse met Echte Data", type="primary"):
    if not top_copper:
        st.warning("Upload aub een Top Copper Gerber (.gbr) om te starten.")
    else:
        with st.spinner("Gerber wordt gelezen en geparseerd in Python (Dit kan even duren)..."):
            
            spatial_data = analyze_real_gerber(top_copper.getvalue())
            
            if "error" in spatial_data:
                st.error(f"Fout bij lezen Gerber: {spatial_data['error']}")
            elif len(spatial_data.get("clusters", [])) == 0:
                st.warning("Geen componenten gevonden met de huidige clustering-instellingen.")
            else:
                st.info(f"{len(spatial_data['clusters'])} pad-clusters gevonden! Verzenden naar Claude (n8n)...")
                
                payload = {"pcb_spatial_data": spatial_data}
                headers = {'Content-Type': 'application/json'}
                
                try:
                    # Verstuur naar n8n
                    response = requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
                    
                    if response.status_code == 200:
                        n8n_data = response.json()
                        raw_text = n8n_data.get("output", "")
                        
                        # Anti-markdown fix
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw_text:
                            raw_text = raw_text.split("```")[1].split("```")[0].strip()
                            
                        ai_result = json.loads(raw_text)
                        
                        st.success("✅ Workflow geslaagd!")
                        st.json(ai_result)
                        
                        output_file = write_raw_gerber_boxes(ai_result)
                        
                        with open(output_file, "rb") as file:
                            st.download_button(
                                label="📥 Download AI Kaders Gerber (.gbr)",
                                data=file,
                                file_name="ai_component_kaders.gbr",
                                mime="application/octet-stream"
                            )
                    else:
                        st.error(f"Fout vanuit n8n (HTTP {response.status_code}): {response.text}")
                except Exception as e:
                    st.error(f"Netwerkfout met n8n: {e}")
