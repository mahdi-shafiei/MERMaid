import streamlit as st
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import os
from PIL import Image

# Display logo
logo_path = Path(__file__).resolve().parent.parent / "Assets" / "MERMAID_logo.png"
try:
    logo = Image.open(logo_path)
    col1, col2 = st.columns([3, 7])
    with col1:
        st.image(logo)
    with col2:
        st.markdown("<h1 style='padding-top: 10px;'>MERMaid Pipeline</h1>", unsafe_allow_html=True)
except Exception as e:
    st.title("MERMaid Pipeline")
    st.warning(f"Logo could not be loaded: {e}")

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
API_URL = "http://127.0.0.1:8000"

# Session flag for saved config
if "config_saved" not in st.session_state:
    st.session_state.config_saved = False

# API key check
if api_key is None:
    st.error("API key is missing. Please add it to your .env file.")
else:
    st.success("API key loaded successfully!")

# Module selector
module = st.radio(
    "Select a module to run:",
    ["VisualHeist", "DataRaider", "VisualHeist + DataRaider", "Full MERMaid Pipeline", "KGWizard (coming soon)"],
    index=0
)

# Load inbuilt keys
response = requests.get(f"{API_URL}/inbuilt_keys")
inbuilt_keys = response.json() if response.status_code == 200 else {}

# Initialize inputs
pdf_dir, image_dir, json_dir = "", "", ""
model_size = "base"
keys = []
new_keys = {}

# Show relevant inputs based on selection
if module in ["VisualHeist", "VisualHeist + DataRaider", "Full MERMaid Pipeline"]:
    pdf_dir = st.text_input("Path to PDF folder", "/absolute/path/to/pdfs")
    image_dir = st.text_input("Directory to save extracted images", "/absolute/path/to/images")
    model_size = st.selectbox("VisualHeist Model Size", ["base", "large"])

if module in ["DataRaider", "VisualHeist + DataRaider", "Full MERMaid Pipeline"]:
    if not image_dir:
        image_dir = st.text_input("Directory with input images", "/absolute/path/to/images")
    json_dir = st.text_input("Output directory for reaction JSONs", "/absolute/path/to/json")

    keys = st.multiselect(
        "Select reaction parameter keys",
        options=list(inbuilt_keys.keys()),
        format_func=lambda x: f"{x} - {inbuilt_keys.get(x, '')}"
    )

    st.markdown("Add custom reaction keys (optional):")
    if "custom_keys" not in st.session_state:
        st.session_state.custom_keys = []

    if st.button("Add Custom Key"):
        st.session_state.custom_keys.append({"key": "", "description": ""})

    for idx, custom_key in enumerate(st.session_state.custom_keys):
        key_input = st.text_input(f"Custom Key {idx+1}", custom_key['key'])
        desc_input = st.text_input(f"Description {idx+1}", custom_key['description'])
        st.session_state.custom_keys[idx] = {"key": key_input, "description": desc_input}
        if key_input and desc_input:
            new_keys[key_input] = desc_input

# Show KGWizard note
if module == "KGWizard (coming soon)":
    st.warning("KGWizard will be supported in a future release.")

# Config dictionary (always constructed for saving)
config = {
    "keys": keys,
    "new_keys": new_keys,
    "pdf_dir": pdf_dir,
    "image_dir": image_dir,
    "json_dir": json_dir,
    "graph_dir": "",  # can update later
    "model_size": model_size,
    "prompt_dir": "",  # backend will handle default
    "kgwizard": {
        "address": "ws://localhost",
        "port": 8182,
        "graph_name": "g",
        "schema": "echem",
        "dynamic_start": 1,
        "dynamic_steps": 5,
        "dynamic_max_workers": 10,
    }
}

# Save configuration button
if st.button("Save Configuration"):
    save_response = requests.post(f"{API_URL}/update_config/", json=config)
    if save_response.status_code == 200:
        st.success("Configuration saved successfully!")
        st.session_state.config_saved = True
    else:
        st.error("Failed to save configuration.")
        st.session_state.config_saved = False

# Run pipeline only if config is saved
if module != "KGWizard (coming soon)":
    if st.session_state.config_saved:
        if st.button("Run Selected Module"):
            try:
                # Call backend based on module
                if module == "VisualHeist":
                    run_response = requests.post(f"{API_URL}/run_visualheist")
                elif module == "DataRaider":
                    run_response = requests.post(f"{API_URL}/run_dataraider")
                elif module == "VisualHeist + DataRaider":
                    vh = requests.post(f"{API_URL}/run_visualheist")
                    dr = requests.post(f"{API_URL}/run_dataraider")
                    run_response = dr if dr.status_code != 200 else vh
                elif module == "Full MERMaid Pipeline":
                    run_response = requests.post(f"{API_URL}/run_all")

                if run_response.status_code == 200:
                    st.success("Module executed successfully.")
                else:
                    st.error(f"Error running pipeline: {run_response.text}")
            except Exception as e:
                st.error(f"Exception occurred: {e}")
    else:
        st.info("Please save your configuration before running any module.")
