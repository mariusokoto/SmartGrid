# ⚡ GDB4SmartGrids

Interface de visualisation et d'optimisation de communautés d'autoconsommation électrique (ACC) sur la commune de **Sartrouville** (2024).

---

## 🎯 Objectif du projet

À partir de données réelles de consommation et production électrique importées dans **Neo4j**, l'application permet de :

1. **Explorer** les bâtiments de Sartrouville sur une carte interactive
2. **Optimiser** la formation de smart grids (communautés d'autoconsommation) via un modèle Julia/JuMP
3. **Visualiser** les résultats : quels bâtiments forment un grid, quel ratio d'autoconsommation locale, quel avantage économique vs l'opérateur réseau

---

## 🏗️ Architecture du projet

```
GDB4SmartGrids/
│
├── app.py                        # Point d'entrée — lance Streamlit
├── config.py                     # Paramètres globaux (Neo4j, chemins, constantes)
├── requirements.txt              # Dépendances Python
│
├── neo4j_db/                     # Couche base de données
│   ├── __init__.py
│   ├── connector.py              # Connexion Neo4j (cachée via @st.cache_resource)
│   └── queries.py                # Toutes les requêtes Cypher
│
├── data/                         # Couche échange de données
│   ├── __init__.py
│   ├── exporter.py               # Neo4j → input.json pour Julia
│   └── tmp/
│       ├── input.json            # Généré automatiquement avant chaque run Julia
│       └── output.json           # Généré par Julia après optimisation
│
├── julia/                        # Couche optimisation
│   ├── __init__.py
│   ├── runner.py                 # Appel subprocess Julia depuis Python
│   ├── mock_optimisation.py      # Simulateur Python (sans Julia) pour les tests
│   └── optimisation.jl           # Modèle JuMP (à brancher quand Julia est prêt)
│
├── map/                          # Couche cartographie
│   ├── __init__.py
│   └── folium_map.py             # Construction des cartes Folium
│
└── ui/                           # Couche interface
    ├── __init__.py
    ├── sidebar.py                # Panneau latéral permanent (paramètres + statut)
    ├── page_exploration.py       # Page 1 — Explorer les données Neo4j
    ├── page_optimisation.py      # Page 2 — Lancer le pipeline d'optimisation
    └── page_resultats.py         # Page 3 — Visualiser et analyser les résultats
```

---

## 📁 Description détaillée des fichiers

### `app.py`
Point d'entrée de l'application Streamlit. Configure la page, initialise le `session_state` (mémoire partagée entre pages), appelle la sidebar et route vers la bonne page selon la navigation.

```bash
streamlit run app.py
```

---

### `config.py`
Fichier de configuration centralisé. **C'est le seul fichier à modifier** pour adapter l'application à ton environnement.

| Variable | Description |
|----------|-------------|
| `NEO4J_URL` | URL de connexion Neo4j (`bolt://localhost:7687`) |
| `NEO4J_USER` | Nom d'utilisateur Neo4j |
| `NEO4J_PASSWORD` | **À renseigner** avec ton mot de passe Neo4j Desktop |
| `VILLE` / `ANNEE` | Sartrouville / 2024 (fixes) |
| `MAP_CENTER_LAT/LON` | Coordonnées de centrage de la carte |
| `JULIA_SCRIPT` | Chemin vers le script Julia |
| `INPUT_PATH` / `OUTPUT_PATH` | Chemins des fichiers d'échange Python ↔ Julia |

---

### `neo4j_db/connector.py`
Gère la connexion à Neo4j. Utilise `@st.cache_resource` pour ne créer qu'une seule connexion par session Streamlit (évite les reconnexions à chaque interaction).

Expose deux fonctions :
- `get_driver()` — retourne le driver Neo4j, affiche un message d'erreur clair si la base est éteinte
- `test_connexion()` — retourne `True/False`, utilisé par la sidebar pour afficher le statut

---

### `neo4j_db/queries.py`
Contient **toutes** les requêtes Cypher, organisées par catégorie. Aucune requête ne doit être écrite ailleurs dans le code.

| Fonction | Description |
|----------|-------------|
| `get_all_buildings()` | Tous les bâtiments avec coordonnées et données annuelles |
| `get_buildings_by_iris()` | Bâtiments filtrés par zone IRIS |
| `get_producers()` | Bâtiments avec `annual_production_kwh > 0` |
| `get_zones_iris()` | Liste des zones IRIS distinctes (pour le sélecteur sidebar) |
| `get_stats_globales()` | KPIs globaux (nb bâtiments, conso totale, prod totale) |
| `get_distances()` | Relations `HAS_DISTANCE` entre bâtiments (attribut `distance_m`) |
| `get_voisins_dans_rayon()` | Voisins d'un bâtiment dans un rayon R |
| `get_energie_par_periode()` | Profil temporel d'un bâtiment (730 périodes × 12h) |
| `get_suppliers()` | Fournisseurs et tarifs |
| `get_contrat_batiment()` | Contrat d'un bâtiment donné |
| `get_grids()` | Grids existants dans Neo4j (après réimport) |
| `importer_resultats_grids()` | Crée les nœuds `:Grid` et relations `:PART_OF` depuis les résultats Julia |

**Schéma Neo4j utilisé :**
```
(:Building)           building_id, address, iris_code, iris_name, type,
                      latitude, longitude, annual_consumption_kwh, annual_production_kwh

(:Period)             period_id, start_time, end_time, time_step

(:Supplier)           supplier_id, name, buy_price

(Building)-[:HAS_DISTANCE {distance_m}]->(Building)
(Building)-[:HAS_ENERGY_DATA {kwh_consumed, kwh_produced, co2_cost}]->(Period)
(Supplier)-[:HAS_CONTRACT {contract_id, tarif_type, price_by_kwh, ...}]->(Building)
(Building)-[:PART_OF]->(Grid)
```

---

### `data/exporter.py`
Prépare le fichier `input.json` envoyé à Julia. Récupère les données depuis Neo4j, filtre les bâtiments sans coordonnées GPS, filtre les distances dépassant le `rayon_max` choisi par l'utilisateur, et calcule le prix de rachat moyen depuis les fournisseurs.

Structure de `input.json` :
```json
{
  "meta":       { "ville", "annee", "nb_batiments", ... },
  "params":     { "min_membres", "rayon_max", "poids_local", "prix_operateur", ... },
  "batiments":  [ { "id", "lat", "lon", "consommation", "production", ... } ],
  "distances":  [ { "from", "to", "metres" } ]
}
```

Expose aussi `valider_output_julia()` qui vérifie que le JSON retourné par Julia contient bien tous les champs attendus.

---

### `julia/runner.py`
Appelle Julia via `subprocess` et gère tous les cas d'erreur : Julia absent du PATH, timeout dépassé, code de retour non nul, fichier output manquant.

- `julia_disponible()` — vérifie que Julia est installé avant d'essayer de lancer
- `run_optimisation()` — lance `julia optimisation.jl input.json output.json` et retourne le dict résultat

---

### `julia/mock_optimisation.py`
**Simulateur Python utilisé pendant les tests, sans avoir Julia installé.**

Contrairement à une assignation aléatoire, il utilise les **vraies distances** `HAS_DISTANCE` de la base Neo4j pour grouper les bâtiments par proximité géographique réelle :

1. Construit un graphe de voisinage depuis les distances filtrées par `rayon_max`
2. Part des **producteurs comme graines** de chaque grid
3. Étend chaque grid avec les voisins les plus proches non encore assignés
4. Calcule le rayon effectif réel (distance max centroïde → membre)
5. Calcule les métriques (ratio local, avantage prix) sur les vraies données

Activé via le toggle **"Mode simulation"** dans la page Optimisation. À désactiver quand `optimisation.jl` est prêt.

---

### `julia/optimisation.jl`
**À implémenter par l'équipe Julia.** Doit :
- Lire `data/tmp/input.json`
- Résoudre le problème d'optimisation avec JuMP (GLPK/HiGHS)
- Écrire `data/tmp/output.json` avec la structure :

```json
{
  "grids": [
    {
      "grid_id": 1,
      "membres": ["bat_001", "bat_002"],
      "local_usage_ratio": 0.74,
      "prix_avantage": 0.03,
      "rayon_effectif": 320.5
    }
  ],
  "batiments_non_assignes": ["bat_009"],
  "runtime_secondes": 2.4
}
```

---

### `map/folium_map.py`
Construit les cartes Folium. Ne se connecte **jamais** directement à Neo4j — reçoit uniquement des listes de dicts Python.

| Fonction | Description |
|----------|-------------|
| `carte_batiments()` | Carte de tous les bâtiments, colorés par type (résidentiel/tertiaire/industrie/agriculture) |
| `carte_grids()` | Carte des résultats d'optimisation, colorée par grid avec cercles de rayon |

---

### `ui/sidebar.py`
Panneau latéral présent sur toutes les pages. Affiche le statut Neo4j, les stats globales, et les contrôles utilisateur.

Retourne un dict `params` consommé par toutes les pages :
```python
{
    "iris_code":      str | None,   # Zone IRIS sélectionnée (None = toutes)
    "iris_name":      str,
    "min_membres":    int,          # Membres minimum par grid
    "rayon_max":      int,          # Rayon maximum en mètres
    "poids_local":    float,        # Poids ratio local (0→1)
    "prix_operateur": float,        # Prix opérateur en €/kWh
}
```

---

### `ui/page_exploration.py`
**Page 1 — Exploration des données.**

Permet d'explorer les données brutes Neo4j sans lancer d'optimisation :
- KPIs globaux (bâtiments, producteurs, conso/prod totale, ratio)
- Carte Folium colorée par type de bâtiment
- Onglet *Répartition* — camembert par type, barres par rôle
- Onglet *Top producteurs* — classement des 20 plus gros producteurs
- Onglet *Profil temporel* — courbe consommation/production sur 730 périodes pour un bâtiment choisi
- Table détaillée avec recherche texte et accès aux contrats fournisseurs

---

### `ui/page_optimisation.py`
**Page 2 — Pipeline d'optimisation en 3 étapes séquentielles.**

```
Étape 1 — Export Neo4j → input.json
          Récupère bâtiments + distances selon les paramètres sidebar
          Filtre les distances > rayon_max
          Aperçu du JSON généré disponible

Étape 2 — Optimisation
          Toggle "Mode simulation" → mock Python (défaut, sans Julia)
          Toggle désactivé         → vrai Julia
          Résumé rapide des résultats (nb grids, ratio moyen, avantage moyen)

Étape 3 — Réimport dans Neo4j
          Crée les nœuds :Grid et relations :PART_OF
          Les résultats deviennent persistants dans la base
```

---

### `ui/page_resultats.py`
**Page 3 — Visualisation et analyse des résultats.**

Charge les résultats depuis `session_state` (run courant) ou depuis Neo4j (runs précédents).

- KPIs globaux des grids formés
- Carte globale de tous les grids
- 4 onglets d'analyse : comparatif, ratio local, avantage prix, tailles
- **Section "Inspecter un grid"** : sélecteur → carte zoomée avec lignes de connexion, table des membres, bilan énergétique
- Table exportable en CSV

---

## 🚀 Installation et lancement

```bash
# 1. Cloner le projet
git clone <repo>
cd GDB4SmartGrids

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer Neo4j
#    → Ouvrir Neo4j Desktop, démarrer la base
#    → Éditer config.py et renseigner NEO4J_PASSWORD

# 4. Lancer
streamlit run app.py
```

---

## 🔄 Flux de données complet

```
Neo4j (base de données)
    │
    ├── get_all_buildings()     → Page Exploration (carte + stats)
    ├── get_energie_par_periode() → Profil temporel
    │
    └── preparer_input_julia()  → data/tmp/input.json
                                        │
                                        ▼
                              julia/optimisation.jl   (ou mock)
                                        │
                                        ▼
                               data/tmp/output.json
                                        │
                              ┌─────────┴──────────┐
                              ▼                     ▼
                    Page Résultats          importer_resultats_grids()
                    (carte + analyse)              │
                                                   ▼
                                            Neo4j (:Grid, :PART_OF)
```

---

## 📦 Dépendances

| Package | Usage |
|---------|-------|
| `streamlit` | Framework interface web |
| `neo4j` | Driver Python pour Neo4j |
| `folium` | Cartes interactives |
| `streamlit-folium` | Intégration Folium dans Streamlit |
| `pandas` | Manipulation des données |
| `plotly` | Graphiques interactifs |

---

## 👥 Équipe

Projet GDB4SmartGrids — UVSQ / ENSIIE 2024-2025
Encadrants : Zoubida Kedad & Stefania Dumbrava
