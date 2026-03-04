# ─────────────────────────────────────────────
#  data/exporter.py  –  Prépare le JSON pour Julia
#  Données : Sartrouville 2024
# ─────────────────────────────────────────────
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import INPUT_PATH
from neo4j_db.queries import (
    get_all_buildings,
    get_buildings_by_iris,
    get_distances,
    get_suppliers,
)


def preparer_input_julia(driver, params: dict) -> dict:
    """
    Récupère les données depuis Neo4j et construit le dict
    d'entrée pour Julia.

    params : dict retourné par render_sidebar()
    {
        iris_code, iris_name, min_membres,
        rayon_max, poids_local, prix_operateur
    }

    Retourne le dict ET l'écrit dans data/tmp/input.json
    """

    # ── 1. Bâtiments ────────────────────────────
    if params["iris_code"]:
        batiments_raw = get_buildings_by_iris(driver, params["iris_code"])
    else:
        batiments_raw = get_all_buildings(driver)

    # Nettoyage et normalisation
    batiments = []
    for b in batiments_raw:
        batiments.append({
            "id"          : b["building_id"],
            "adresse"     : b.get("adresse", ""),
            "iris_code"   : b.get("iris_code", ""),
            "iris_name"   : b.get("iris_name", ""),
            "type"        : b.get("type", ""),
            "lat"         : float(b["lat"]) if b["lat"] else None,
            "lon"         : float(b["lon"]) if b["lon"] else None,
            "consommation": float(b["consommation"]) if b["consommation"] else 0.0,
            "production"  : float(b["production"])   if b["production"]   else 0.0,
        })

    # Filtre les bâtiments sans coordonnées (ne peuvent pas être placés sur la carte)
    batiments_valides = [b for b in batiments if b["lat"] and b["lon"]]
    ids_valides = {b["id"] for b in batiments_valides}

    # ── 2. Distances ────────────────────────────
    distances_raw = get_distances(driver, params["iris_code"])

    # Garde uniquement les distances entre bâtiments valides
    # et dans la limite du rayon max choisi par l'utilisateur
    distances = [
        {
            "from"  : d["from_id"],
            "to"    : d["to_id"],
            "metres": float(d["metres"]),
        }
        for d in distances_raw
        if (
            d["from_id"] in ids_valides
            and d["to_id"] in ids_valides
            and d["metres"] is not None
            and d["metres"] <= params["rayon_max"]
        )
    ]

    # ── 3. Fournisseurs (prix de référence) ─────
    try:
        suppliers = get_suppliers(driver)
        # Prix moyen de rachat comme référence
        buy_prices = [s["buy_price"] for s in suppliers if s["buy_price"]]
        prix_rachat_moyen = sum(buy_prices) / len(buy_prices) if buy_prices else 0.08
    except Exception:
        prix_rachat_moyen = 0.08

    # ── 4. Construction du payload ───────────────
    payload = {
        "meta": {
            "ville"       : "Sartrouville",
            "annee"       : 2024,
            "iris_code"   : params["iris_code"],
            "iris_name"   : params["iris_name"],
            "nb_batiments": len(batiments_valides),
            "nb_distances": len(distances),
        },
        "params": {
            "min_membres"   : params["min_membres"],
            "rayon_max"     : params["rayon_max"],
            "poids_local"   : params["poids_local"],
            "poids_prix"    : round(1.0 - params["poids_local"], 4),
            "prix_operateur": params["prix_operateur"],
            "prix_rachat"   : round(prix_rachat_moyen, 4),
        },
        "batiments" : batiments_valides,
        "distances" : distances,
    }

    # ── 5. Écriture du fichier JSON ──────────────
    os.makedirs(os.path.dirname(INPUT_PATH), exist_ok=True)
    with open(INPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def valider_output_julia(output: dict) -> tuple[bool, str]:
    """
    Vérifie que le JSON retourné par Julia est bien formé.
    Retourne (True, "") si valide, (False, message) sinon.
    """
    champs_requis = ["grids", "batiments_non_assignes", "runtime_secondes"]
    for champ in champs_requis:
        if champ not in output:
            return False, f"Champ manquant dans l'output Julia : '{champ}'"

    for i, grid in enumerate(output["grids"]):
        champs_grid = ["grid_id", "membres", "local_usage_ratio", "prix_avantage", "rayon_effectif"]
        for champ in champs_grid:
            if champ not in grid:
                return False, f"Champ manquant dans le grid {i} : '{champ}'"

    return True, ""