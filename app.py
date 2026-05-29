import streamlit as st
import requests
import json
# import gerbonara (Zorg dat dit in je requirements.txt staat)

# --- CONFIGURATIE ---
# Vervang dit door de Test- of Production Webhook URL uit je n8n start-node
N8N_WEBHOOK_URL = "https://jouw-n8n-instantie.n8n.cloud/webhook/start-stencil-ai"

st.set_page_config(page_title="Stencil AI Portal", layout="wide")
st.title("EMS Stencil Design AI")
st.markdown("Upload de PCB-data. De AI-agenten ontwerpen het stencil en sturen het resultaat per mail.")

# --- UI ELEMENTEN ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Bestand Upload")
    top_copper = st.file_uploader("Top Copper (.gbr)", type=['gbr'])
    solder_mask = st.file_uploader("Top Solder Mask (.gbr)", type=['gbr'])

with col2:
    st.subheader("2. Klantspecifieke Regels")
    thickness = st.number_input("Basis Stencildikte (micron)", value=120)
    extra_rules = st.text_area("DFM Regels", value="BGA met pitch < 0.5mm: print 55% van pitch binnen relief. Zeer kleine soldermask relief -> inverted homeplate.")

# --- FUNCTIES ---
def parse_gerber_to_json(copper_file, mask_file):
    """
    Dit is de plek waar je Gerbonara gebruikt om de coördinaten te extraheren.
    Voor deze opzet sturen we een gestructureerde 'dummy' JSON terug die je AI kan lezen.
    """
    # In productie: copper = gerbonara.GerberFile.load(copper_file)
    
    mock_data = {
        "metadata": {"base_thickness_um": thickness},
        "raw_pads": [
            {"id": "pad_1", "x": 10.5, "y": 20.1, "shape": "circle", "size_mm": 0.25},
            {"id": "pad_2", "x": 10.9, "y": 20.1, "shape": "circle", "size_mm": 0.25},
            # etc...
        ]
    }
    return mock_data

# --- ACTIE ---
if st.button("Start Agentic Design Workflow", type="primary"):
    if not top_copper or not solder_mask:
        st.error("Upload a.u.b. zowel Koper als Soldeermasker bestanden.")
    else:
        with st.spinner("Gerber bestanden analyseren en doorsturen naar n8n..."):
            
            # 1. Converteer de fysieke bestanden naar data (JSON)
            pcb_data = parse_gerber_to_json(top_copper, solder_mask)
            
            # 2. Maak het pakketje (payload) voor n8n
            payload = {
                "pcb_data": pcb_data,
                "rules": extra_rules
            }
            
            # 3. Schiet het naar de n8n Webhook
            headers = {'Content-Type': 'application/json'}
            try:
                response = requests.post(N8N_WEBHOOK_URL, data=json.dumps(payload), headers=headers)
                
                if response.status_code == 200:
                    st.success("✅ Data succesvol ontvangen door de AI! De agents zijn aan het werk. Houd je mailbox in de gaten voor eventuele Human-in-the-Loop vragen of het definitieve PDF-rapport.")
                else:
                    st.error(f"Fout bij communicatie met n8n: HTTP {response.status_code}")
            except Exception as e:
                st.error(f"Verbindingsfout: {e}")
