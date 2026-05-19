import os
import streamlit as st

st.set_page_config(page_title="riot.txt", page_icon="📄", layout="centered")

try:
    riot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "riot.txt")
    with open(riot_path, "r") as f:
        content = f.read().strip()
except Exception:
    content = ""

st.markdown(f"""<pre>{content}</pre>""", unsafe_allow_html=True)
