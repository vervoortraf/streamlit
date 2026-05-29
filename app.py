import streamlit as st
import requests
import json
import tempfile
import os
import gerbonara

# --- CONFIGURATIE ---
N8N_WEBHOOK_URL = "https://ravoortt.app.n8n.cloud/webhook-test/ff70e4f4-afb8-4faa-91b9-bb4046bdc2c9"

st.set_page_config(page_title="AI Gerber Analist (Puur AI Logica)", layout="wide")
st.title("Stap 2: AI als het Brein")

st.info("Upload je Top Copper (.gbr). Python leest enkel de rauwe coördinaten. De AI doet 100% van het cluster- en denkwerk.")

top_copper = st.file_uploader("Upload Top Copper Gerber (.gbr)", type=['gbr', 'pho', 'art'])

def extract_raw_pads(gerber_bytes):
    """
    Python als de 'ogen'. Het haalt puur de X/Y locaties op, ZONDER enige logica of clustering toe te passen.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gbr") as tmp:
        tmp.write(gerber_bytes)
        tmp_path = tmp.name

    try:
        layer = gerbonara.rs274x.GerberFile.open(tmp_path)
        
        raw_pads = []
        pad_id = 0
        
        # We halen domweg elke 'Flash' (pad) op
        for obj in layer.objects:
            if type(obj).__name__ == 'Flash':
                # We ronden af op 3 decimalen om de payload naar n8n compact te houden
                raw_pads.append({
                    "id": pad_id,
                    "x": round(obj.x, 3),
                    "y": round(obj.y, 3)
                })
                pad_id += 1

        os.remove(tmp_path)
        
        if not raw_pads:
            return {"error": "Geen pads gevonden. Zorg dat het de juiste Gerber-laag is."}
            
        # Ter bescherming van de AI token limiet tijdens deze test, sturen we max 500 pads.
        # In een zware productieomgeving kun je dit verhogen, mits je AI-model de context-lengte aankan.
        if len(raw_pads) > 2000:
            st.warning(f"Let op: Deze printplaat heeft {len(raw_pads)} pads. Voor deze test sturen we er 2000 naar Claude om een API-timeout te voorkomen.")
            raw_pads = raw_pads[:2000]

        return {"raw_pads": raw_pads}

    except Exception as e:
        if os.path.exists(tmp_path): os.remove(tmp_path)
        return {"error": str(e)}

def write_raw_gerber_boxes(recognized_data, output_filename="ai_component_kaders.gbr"):
    """
    Python als de 'handen'. Tekent de door de AI bedachte kaders in RS-274X.
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
        
        # Marge om het kader iets groter te maken dan het koper
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
if st.button("Start AI Analyse (Puur Brein)", type="primary"):
    if not top_copper:
        st.warning("Upload aub een Top Copper Gerber (.gbr) om te starten.")
    else:
        with st.spinner("Python extraheert de rauwe coördinaten..."):
            
            spatial_data = extract_raw_pads(top_copper.getvalue())
            
            if "error" in spatial_data:
                st.error(f"Fout: {spatial_data['error']}")
            else:
                pad_count = len(spatial_data['raw_pads'])
                st.info(f"{pad_count} ongefilterde pads gevonden. Claude gaat nu nadenken (dit duurt even)...")
                
                payload = {"pcb_spatial_data": spatial_data}
                headers = {'Content-Type': 'application/json'}
                
                try:
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
                        
                        st.success("✅ AI heeft de logica toegepast en de componenten samengesteld!")
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
