import os
import streamlit as st

st.set_page_config(page_title="riot.txt", page_icon="📄", layout="centered")

try:
    riot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "riot.txt")
    with open(riot_path, "r") as f:
        content = f.read().strip()
except Exception:
    content = ""

st.markdown(f"""
<style>
    #stDecoration {{ display: none !important; }}
    header {{ display: none !important; }}
    [data-testid="stSidebar"] {{ display: none !important; }}
    #MainMenu {{ display: none !important; }}
    footer {{ display: none !important; }}
    .stApp {{ background: #0e1117; }}
    .block-container {{ padding: 2rem !important; max-width: 800px; }}
</style>
<pre style="
    font-size: 16px;
    font-family: 'Courier New', monospace;
    color: #e0e0e0;
    background: #1a1d23;
    padding: 16px;
    border-radius: 8px;
    border: 1px solid #333;
    white-space: pre-wrap;
    word-wrap: break-word;
">{content}</pre>
""", unsafe_allow_html=True)
