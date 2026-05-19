import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "riot.txt"), "r") as f:
        content = f.read().strip()
except Exception:
    content = ""

import streamlit as st
st.set_page_config(page_title="riot.txt", page_icon="📄", layout="centered")

st.markdown(f"""
<style>
    #root > div:first-child > div:first-child > div:first-child > div:first-child {{
        display: none !important;
    }}
    .stApp .stAppHeader, .stApp .stAppSidebar, .stApp .stAppToolbar {{
        display: none !important;
    }}
    header, footer, .stActionButton, [data-testid="stSidebar"], .eczjsme10, .eczjsme11 {{
        display: none !important;
    }}
    body, .stApp, .main, .block-container {{
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        background: #0f0c29 !important;
    }}
    .stMarkdown {{
        padding: 40px !important;
    }}
    pre {{
        font-size: 20px;
        font-family: monospace;
        color: #e0e0e0;
        background: #0f0c29;
        border: none;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
</style>
<pre>{content}</pre>
""", unsafe_allow_html=True)
