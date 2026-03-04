# ─────────────────────────────────────────────
#  app.py  –  Point d'entrée Streamlit
#  GDB4SmartGrids — Sartrouville 2024
# ─────────────────────────────────────────────
import streamlit as st
import sys, os

# Assure que tous les modules sont accessibles
sys.path.append(os.path.dirname(__file__))

from ui.sidebar import render_sidebar
from ui import page_exploration, page_optimisation, page_resultats

# ── Configuration de la page ─────────────────
st.set_page_config(
    page_title="GDB4SmartGrids",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialisation session_state ─────────────
if "results" not in st.session_state:
    st.session_state["results"] = None

if "payload" not in st.session_state:
    st.session_state["payload"] = None

if "export_ok" not in st.session_state:
    st.session_state["export_ok"] = False

# ── Sidebar + navigation ─────────────────────
params = render_sidebar()

st.sidebar.divider()
page = st.sidebar.radio(
    "Navigation",
    options=["🗺️ Exploration", "⚙️ Optimisation", "📊 Résultats"],
    index=0,
)

# ── Routage ──────────────────────────────────
if page == "🗺️ Exploration":
    page_exploration.render(params)

elif page == "⚙️ Optimisation":
    page_optimisation.render(params)

elif page == "📊 Résultats":
    page_resultats.render(params)