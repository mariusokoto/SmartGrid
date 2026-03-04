# ─────────────────────────────────────────────
#  config.example.py
#  Copie ce fichier en config.py et remplis
#  les valeurs avant de lancer l'application.
#
#  cp config.example.py config.py
# ─────────────────────────────────────────────

# --- Neo4j ---
NEO4J_URL      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "mot de passe"

# --- Données (fixes) ---
VILLE  = "Sartrouville"
ANNEE  = 2024

# --- Carte ---
MAP_CENTER_LAT = 48.9372
MAP_CENTER_LON = 2.1628
MAP_ZOOM       = 14

# --- Julia ---
JULIA_SCRIPT = "julia/optimisation.jl"

# --- Fichiers temporaires ---
INPUT_PATH  = "data/tmp/input.json"
OUTPUT_PATH = "data/tmp/output.json"
