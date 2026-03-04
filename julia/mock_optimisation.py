# ─────────────────────────────────────────────
#  julia/mock_optimisation.py
#  Simule Julia en groupant les bâtiments
#  par PROXIMITÉ GÉOGRAPHIQUE RÉELLE
#  (utilise les distances de input.json)
# ─────────────────────────────────────────────
import json
import time
import math
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import INPUT_PATH, OUTPUT_PATH


def _distance_euclidienne(b1: dict, b2: dict) -> float:
    """Distance en mètres entre deux bâtiments via leurs coordonnées GPS."""
    R = 6_371_000  # rayon terre en mètres
    lat1, lon1 = math.radians(b1["lat"]), math.radians(b1["lon"])
    lat2, lon2 = math.radians(b2["lat"]), math.radians(b2["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _rayon_effectif(membres_coords: list[tuple]) -> float:
    """Rayon effectif = distance max entre le centroïde et un membre."""
    if len(membres_coords) < 2:
        return 0.0
    lat_c = sum(c[0] for c in membres_coords) / len(membres_coords)
    lon_c = sum(c[1] for c in membres_coords) / len(membres_coords)
    return max(
        _distance_euclidienne(
            {"lat": lat_c, "lon": lon_c},
            {"lat": c[0], "lon": c[1]}
        )
        for c in membres_coords
    )


def run_mock_optimisation() -> dict:
    """
    Lit input.json, groupe les bâtiments par proximité réelle
    en utilisant les distances HAS_DISTANCE de la base,
    puis écrit output.json.
    """

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    batiments  = payload["batiments"]
    distances  = payload["distances"]
    params     = payload["params"]

    min_membres  = params["min_membres"]
    rayon_max    = params["rayon_max"]
    poids_local  = params["poids_local"]
    prix_op      = params["prix_operateur"]

    debut = time.time()

    # ── Index des bâtiments ──────────────────────
    bat_index = {b["id"]: b for b in batiments}

    # ── Graphe de voisinage (dans le rayon max) ──
    # voisins[id] = liste des ids voisins dans le rayon
    voisins = defaultdict(set)
    for d in distances:
        if d["metres"] is not None and d["metres"] <= rayon_max:
            voisins[d["from"]].add(d["to"])
            voisins[d["to"]].add(d["from"])

    # ── Algorithme de clustering par voisinage ───
    # On part des bâtiments producteurs comme "graines"
    # puis on étend avec leurs voisins les plus proches
    assignes  = set()
    grids     = []
    grid_id   = 1

    # Trier : producteurs d'abord comme graines
    producteurs = [b for b in batiments if b["production"] > 0]
    autres      = [b for b in batiments if b["production"] == 0]
    ordre       = producteurs + autres

    for bat_seed in ordre:
        sid = bat_seed["id"]
        if sid in assignes:
            continue

        # Trouve les voisins non assignés dans le rayon
        candidats = [
            v for v in voisins[sid]
            if v not in assignes and v in bat_index
        ]

        # Trie les candidats par distance réelle au seed
        candidats_avec_dist = []
        for cid in candidats:
            b2 = bat_index[cid]
            dist = _distance_euclidienne(bat_seed, b2)
            if dist <= rayon_max:
                candidats_avec_dist.append((cid, dist))

        candidats_avec_dist.sort(key=lambda x: x[1])

        # Construit le groupe seed + voisins proches
        membres = [sid]
        for cid, dist in candidats_avec_dist:
            if cid not in assignes:
                membres.append(cid)

        if len(membres) < min_membres:
            # Pas assez de voisins → on essaie quand même
            # d'atteindre min_membres en cherchant plus loin
            # (dans la limite du rayon max global)
            for b2 in autres:
                if len(membres) >= min_membres:
                    break
                bid2 = b2["id"]
                if bid2 not in assignes and bid2 not in membres:
                    dist = _distance_euclidienne(bat_seed, b2)
                    if dist <= rayon_max:
                        membres.append(bid2)

        if len(membres) < min_membres:
            # Toujours pas assez → non assigné
            continue

        # Marque comme assignés
        for m in membres:
            assignes.add(m)

        # Calcule les métriques du grid
        membres_coords = [
            (bat_index[m]["lat"], bat_index[m]["lon"])
            for m in membres if m in bat_index
        ]
        rayon = round(_rayon_effectif(membres_coords), 1)

        conso_grid = sum(bat_index[m]["consommation"] for m in membres if m in bat_index)
        prod_grid  = sum(bat_index[m]["production"]   for m in membres if m in bat_index)

        local_usage_ratio = round(
            min(1.0, prod_grid / conso_grid) if conso_grid > 0 else 0.0,
            4
        )

        # Avantage prix : économie vs opérateur sur la prod locale autoconsommée
        prod_autoconsommee = min(prod_grid, conso_grid)
        prix_avantage = round(
            (prix_op - params["prix_rachat"]) * (prod_autoconsommee / conso_grid)
            if conso_grid > 0 else 0.0,
            4
        )

        grids.append({
            "grid_id"           : grid_id,
            "membres"           : membres,
            "local_usage_ratio" : local_usage_ratio,
            "prix_avantage"     : prix_avantage,
            "rayon_effectif"    : rayon,
        })
        grid_id += 1

    # Bâtiments non assignés
    non_assignes = [b["id"] for b in batiments if b["id"] not in assignes]

    runtime = round(time.time() - debut, 3)

    output = {
        "grids"                  : grids,
        "batiments_non_assignes" : non_assignes,
        "runtime_secondes"       : runtime,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output