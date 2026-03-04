# ─────────────────────────────────────────────
#  config.py  –  Paramètres globaux du projet
# ─────────────────────────────────────────────

# --- Neo4j ---
NEO4J_URL      = "neo4j://127.0.0.1:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "SmartGrid2026" 

# --- Données (fixes : une seule ville, une seule année) ---
VILLE  = "Sartrouville"
ANNEE  = 2024

# --- Carte : centroïde de Sartrouville ---
MAP_CENTER_LAT = 48.9372
MAP_CENTER_LON = 2.1628
MAP_ZOOM       = 14

# --- Julia ---
JULIA_SCRIPT = "julia/optimisation.jl"

# --- Fichiers temporaires d'échange Python ↔ Julia ---
INPUT_PATH  = "data/tmp/input.json"
OUTPUT_PATH = "data/tmp/output.json"