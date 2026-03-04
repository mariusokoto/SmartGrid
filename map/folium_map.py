# ─────────────────────────────────────────────
#  map/folium_map.py  –  Carte Folium
#  Données : Sartrouville 2024
# ─────────────────────────────────────────────
import folium
from folium.plugins import MarkerCluster
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import MAP_CENTER_LAT, MAP_CENTER_LON, MAP_ZOOM

# Palette de couleurs pour différencier les grids
COULEURS_GRIDS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45",
    "#fabed4", "#469990", "#dcbeff", "#9A6324",
]

# Couleurs par type de bâtiment
COULEURS_TYPE = {
    "RESIDENTIEL": "#2563eb",
    "TERTIAIRE":   "#f59e0b",
    "INDUSTRIE":   "#dc2626",
    "AGRICULTURE": "#16a34a",
}

# Icônes par rôle
ICONE_ROLE = {
    "Consumer": "🔋",
    "Producer": "☀️",
    "Prosumer": "⚡",
}


def _couleur_grid(grid_id) -> str:
    return COULEURS_GRIDS[int(grid_id) % len(COULEURS_GRIDS)]


def _role_label(b: dict) -> str:
    return "Producteur" if (b.get("production") or 0) > 0 else "Consommateur"


def _couleur_type(building_type: str) -> str:
    return COULEURS_TYPE.get(str(building_type).upper(), "#6b7280")


# ══════════════════════════════════════════════
#  CARTE 1 — Bâtiments bruts (depuis Neo4j)
# ══════════════════════════════════════════════

def carte_batiments(batiments: list[dict]) -> folium.Map:
    """
    Affiche tous les bâtiments de Sartrouville sur la carte.
    Couleur = type de bâtiment (résidentiel, tertiaire, industrie, agriculture).
    Popup = adresse, iris, consommation, production, rôle.

    batiments : résultat de get_all_buildings() ou get_buildings_by_iris()
      champs : building_id, adresse, iris_code, iris_name, type,
               lat, lon, consommation, production, labels
    """
    carte = folium.Map(location=[MAP_CENTER_LAT, MAP_CENTER_LON], zoom_start=MAP_ZOOM)
    cluster = MarkerCluster().add_to(carte)

    for b in batiments:
        role   = _role_label(b)
        icone  = "☀️" if role == "Producteur" else "🔋"
        couleur = _couleur_type(b.get("type", ""))

        conso = b.get("consommation") or 0
        prod  = b.get("production") or 0

        popup_html = f"""
        <div style="font-family:sans-serif;font-size:13px;min-width:200px">
            <b>{b.get('address', b['building_id'])}</b><br>
            <span style="color:#6b7280">{b.get('iris_name', '')} — {b.get('type', '')}</span><br><br>
            {icone} Rôle : <b>{role}</b><br>
            🔋 Consommation : <b>{conso:,.0f} kWh</b><br>
            ☀️ Production   : <b>{prod:,.0f} kWh</b>
        </div>
        """

        folium.CircleMarker(
            location=[b["lat"], b["lon"]],
            radius=5,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=b.get("address", b["building_id"]),
        ).add_to(cluster)

    # Légende types
    _ajouter_legende_types(carte)

    return carte


# ══════════════════════════════════════════════
#  CARTE 2 — Grids (résultats d'optimisation)
# ══════════════════════════════════════════════

def carte_grids(batiments: list[dict], grids: list[dict]) -> folium.Map:
    """
    Affiche les bâtiments colorés par grid + cercle de rayon effectif.

    batiments : résultat de get_all_buildings()
    grids     : résultat de run_optimisation() ou get_grids()
      champs  : grid_id, membres, local_usage_ratio, prix_avantage, rayon_effectif
    """
    bat_index  = {b["building_id"]: b for b in batiments}
    bat_to_grid = {}
    for grid in grids:
        for bat_id in grid["membres"]:
            bat_to_grid[bat_id] = grid

    carte = folium.Map(location=[MAP_CENTER_LAT, MAP_CENTER_LON], zoom_start=MAP_ZOOM)

    # Cercles de rayon par grid
    for grid in grids:
        membres_coords = [
            (bat_index[m]["lat"], bat_index[m]["lon"])
            for m in grid["membres"]
            if m in bat_index
        ]
        if not membres_coords:
            continue

        lat_c   = sum(c[0] for c in membres_coords) / len(membres_coords)
        lon_c   = sum(c[1] for c in membres_coords) / len(membres_coords)
        couleur = _couleur_grid(grid["grid_id"])

        folium.Circle(
            location=[lat_c, lon_c],
            radius=grid["rayon_effectif"],
            color=couleur,
            fill=True,
            fill_opacity=0.07,
            tooltip=(
                f"Grid {grid['grid_id']} | "
                f"{len(grid['membres'])} bâtiments | "
                f"rayon {grid['rayon_effectif']} m"
            ),
        ).add_to(carte)

    # Markers des bâtiments
    for b in batiments:
        grid    = bat_to_grid.get(b["building_id"])
        role    = _role_label(b)
        icone   = "☀️" if role == "Producteur" else "🔋"
        conso   = b.get("consommation") or 0
        prod    = b.get("production") or 0

        if grid:
            couleur = _couleur_grid(grid["grid_id"])
            popup_html = f"""
            <div style="font-family:sans-serif;font-size:13px;min-width:220px">
                <b>{b.get('address', b['building_id'])}</b><br>
                <span style="color:#6b7280">{b.get('iris_name', '')}</span><br><br>
                🗂️ Grid : <b>{grid['grid_id']}</b><br>
                {icone} Rôle : <b>{role}</b><br>
                🔋 Conso : <b>{conso:,.0f} kWh</b><br>
                ☀️ Prod  : <b>{prod:,.0f} kWh</b><br><br>
                📊 Local usage ratio : <b>{grid['local_usage_ratio']:.1%}</b><br>
                💰 Avantage prix     : <b>{grid['prix_avantage']:.3f} €/kWh</b>
            </div>
            """
        else:
            couleur = "#6b7280"
            popup_html = f"""
            <div style="font-family:sans-serif;font-size:13px">
                <b>{b.get('address', b['building_id'])}</b><br>
                ⚠️ Non assigné à un grid<br>
                🔋 Conso : {conso:,.0f} kWh
            </div>
            """

        folium.CircleMarker(
            location=[b["lat"], b["lon"]],
            radius=6,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=b.get("address", b["building_id"]),
        ).add_to(carte)

    # Légende grids
    _ajouter_legende_grids(carte, grids)

    return carte


# ══════════════════════════════════════════════
#  LÉGENDES
# ══════════════════════════════════════════════

def _ajouter_legende_types(carte: folium.Map):
    lignes = "".join([
        f"""<div style="display:flex;align-items:center;margin-bottom:4px">
            <div style="width:12px;height:12px;border-radius:50%;
                        background:{c};margin-right:8px"></div>{t}
        </div>"""
        for t, c in COULEURS_TYPE.items()
    ])
    html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                background:white;padding:12px 16px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2);font-family:sans-serif;font-size:13px">
        <b>Type de bâtiment</b><br><br>{lignes}
    </div>"""
    carte.get_root().html.add_child(folium.Element(html))


def _ajouter_legende_grids(carte: folium.Map, grids: list[dict]):
    lignes = "".join([
        f"""<div style="display:flex;align-items:center;margin-bottom:4px">
            <div style="width:12px;height:12px;border-radius:50%;
                        background:{_couleur_grid(g['grid_id'])};margin-right:8px"></div>
            Grid {g['grid_id']} — {len(g['membres'])} bâtiments
        </div>"""
        for g in grids
    ])
    lignes += """<div style="display:flex;align-items:center;margin-top:4px">
        <div style="width:12px;height:12px;border-radius:50%;
                    background:#6b7280;margin-right:8px"></div>Non assigné
    </div>"""
    html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                background:white;padding:12px 16px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2);font-family:sans-serif;font-size:13px">
        <b>Smart Grids — Sartrouville 2024</b><br><br>{lignes}
    </div>"""
    carte.get_root().html.add_child(folium.Element(html))