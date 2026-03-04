# ─────────────────────────────────────────────
#  ui/sidebar.py  –  Panneau latéral permanent
#  Données : Sartrouville 2024
# ─────────────────────────────────────────────
import streamlit as st
from neo4j_db.connector import get_driver, test_connexion
from neo4j_db.queries import get_zones_iris, get_stats_globales


def render_sidebar() -> dict:
    """
    Affiche la sidebar et retourne un dict avec tous les paramètres
    choisis par l'utilisateur.

    Retourne :
    {
        "iris_code"    : str | None,   # zone IRIS sélectionnée (None = toutes)
        "iris_name"    : str,          # nom lisible de la zone
        "min_membres"  : int,          # paramètre Julia
        "rayon_max"    : int,          # paramètre Julia (mètres)
        "poids_local"  : float,        # paramètre Julia (0.0 → 1.0)
        "prix_operateur: float,        # paramètre Julia (€/kWh)
    }
    """

    st.sidebar.title("⚡ GDB4SmartGrids")
    st.sidebar.caption("Sartrouville — 2024")
    st.sidebar.divider()

    # ── Statut connexion Neo4j ──────────────────
    st.sidebar.subheader("🗄️ Base de données")
    connecte = test_connexion()
    if connecte:
        st.sidebar.success("Neo4j connecté ✅")
    else:
        st.sidebar.error("Neo4j déconnecté ❌")
        st.sidebar.info("Démarre la base dans Neo4j Desktop puis recharge la page.")
        # Retourne des valeurs par défaut si pas de connexion
        return _valeurs_defaut()

    # ── Statistiques globales ───────────────────
    driver = get_driver()
    try:
        stats = get_stats_globales(driver)
        col1, col2 = st.sidebar.columns(2)
        col1.metric("Bâtiments", f"{stats['nb_batiments']:,}")
        col2.metric("Producteurs", f"{stats['nb_producteurs']:,}")
    except Exception:
        pass

    st.sidebar.divider()

    # ── Filtre zone IRIS ────────────────────────
    st.sidebar.subheader("🗺️ Zone d'analyse")

    try:
        zones = get_zones_iris(driver)
        options_zones = [{"label": "Toutes les zones", "code": None}] + [
            {"label": z["iris_name"], "code": z["iris_code"]} for z in zones
        ]
        labels_zones = [z["label"] for z in options_zones]

        choix_zone = st.sidebar.selectbox(
            "Zone IRIS",
            options=range(len(options_zones)),
            format_func=lambda i: labels_zones[i],
            index=0,
        )
        iris_selectionne = options_zones[choix_zone]

    except Exception:
        st.sidebar.warning("Impossible de charger les zones IRIS.")
        iris_selectionne = {"label": "Toutes les zones", "code": None}

    st.sidebar.divider()

    # ── Paramètres d'optimisation Julia ────────
    st.sidebar.subheader("⚙️ Paramètres d'optimisation")

    min_membres = st.sidebar.slider(
        "Membres minimum par grid",
        min_value=2,
        max_value=10,
        value=3,
        step=1,
        help="Nombre minimum de bâtiments pour former un grid.",
    )

    rayon_max = st.sidebar.slider(
        "Rayon maximum (m)",
        min_value=100,
        max_value=2000,
        value=500,
        step=50,
        help="Distance maximale entre deux bâtiments d'un même grid (max 2 km selon HAS_DISTANCE).",
    )

    st.sidebar.caption("Pondération de l'objectif")
    poids_local = st.sidebar.slider(
        "Poids ratio local ↔ avantage prix",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.05,
        help=(
            "0.0 = optimise uniquement l'avantage prix\n"
            "1.0 = optimise uniquement le ratio de consommation locale"
        ),
    )
    # Affiche les deux poids pour que l'utilisateur comprenne
    c1, c2 = st.sidebar.columns(2)
    c1.caption(f"🏠 Local : **{poids_local:.0%}**")
    c2.caption(f"💰 Prix  : **{1 - poids_local:.0%}**")

    prix_operateur = st.sidebar.number_input(
        "Prix opérateur (€/kWh)",
        min_value=0.05,
        max_value=0.50,
        value=0.18,
        step=0.01,
        format="%.2f",
        help="Prix de référence du fournisseur contre lequel on compare l'avantage du grid.",
    )

    st.sidebar.divider()
    st.sidebar.caption("Projet GDB4SmartGrids — UVSQ / ENSIIE 2024-2025")

    return {
        "iris_code"     : iris_selectionne["code"],
        "iris_name"     : iris_selectionne["label"],
        "min_membres"   : min_membres,
        "rayon_max"     : rayon_max,
        "poids_local"   : poids_local,
        "prix_operateur": prix_operateur,
    }


def _valeurs_defaut() -> dict:
    """Valeurs de secours si Neo4j est inaccessible."""
    return {
        "iris_code"     : None,
        "iris_name"     : "Toutes les zones",
        "min_membres"   : 3,
        "rayon_max"     : 500,
        "poids_local"   : 0.6,
        "prix_operateur": 0.18,
    }