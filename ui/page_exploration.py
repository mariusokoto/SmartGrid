# ─────────────────────────────────────────────
#  ui/page_exploration.py  –  Exploration des données Neo4j
#  Données : Sartrouville 2024
# ─────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j_db.connector import get_driver
from neo4j_db.queries import (
    get_all_buildings,
    get_buildings_by_iris,
    get_producers,
    get_energie_par_periode,
    get_contrat_batiment,
    get_stats_globales,
)
from map.folium_map import carte_batiments


def render(params: dict):
    """
    Page 1 — Exploration des données.
    params : dict retourné par render_sidebar()
    """

    st.title("🗺️ Exploration — Sartrouville 2024")

    driver = get_driver()
    if driver is None:
        st.error("Impossible de se connecter à Neo4j.")
        return

    # ── Chargement des bâtiments ────────────────
    with st.spinner("Chargement des bâtiments depuis Neo4j..."):
        if params["iris_code"]:
            batiments = get_buildings_by_iris(driver, params["iris_code"])
        else:
            batiments = get_all_buildings(driver)

    if not batiments:
        st.warning("Aucun bâtiment trouvé pour cette zone.")
        return

    # ── KPIs en haut de page ────────────────────
    st.subheader(f"📊 Vue d'ensemble — {params['iris_name']}")
    _afficher_kpis(batiments)
    st.divider()

    # ── Carte Folium ────────────────────────────
    st.subheader("🗺️ Carte des bâtiments")
    _afficher_legende_types()
    carte = carte_batiments(batiments)
    st_folium(carte, width="100%", height=500, returned_objects=[])
    st.divider()

    # ── Graphiques ──────────────────────────────
    st.subheader("📈 Analyses")
    tab1, tab2, tab3 = st.tabs([
        "Répartition par type",
        "Top producteurs",
        "Profil temporel",
    ])

    with tab1:
        _onglet_repartition(batiments)

    with tab2:
        _onglet_producteurs(driver)

    with tab3:
        _onglet_profil_temporel(driver, batiments)

    st.divider()

    # ── Table détaillée ─────────────────────────
    st.subheader("📋 Données détaillées")
    _afficher_table(batiments, driver)


# ══════════════════════════════════════════════
#  BLOCS INTERNES
# ══════════════════════════════════════════════

def _afficher_kpis(batiments: list[dict]):
    df = pd.DataFrame(batiments)

    nb_total     = len(df)
    nb_prod      = (df["production"].fillna(0) > 0).sum()
    conso_totale = df["consommation"].fillna(0).sum()
    prod_totale  = df["production"].fillna(0).sum()
    ratio_local  = prod_totale / conso_totale if conso_totale > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bâtiments",    f"{nb_total:,}")
    c2.metric("Producteurs",  f"{nb_prod:,}")
    c3.metric("Conso totale", f"{conso_totale/1e6:.2f} GWh")
    c4.metric("Prod totale",  f"{prod_totale/1e6:.2f} GWh")
    c5.metric("Ratio local",  f"{ratio_local:.1%}")


def _afficher_legende_types():
    couleurs = {
        "RESIDENTIEL": "#2563eb",
        "TERTIAIRE":   "#f59e0b",
        "INDUSTRIE":   "#dc2626",
        "AGRICULTURE": "#16a34a",
    }
    html = " &nbsp; ".join([
        f'<span style="display:inline-flex;align-items:center;gap:5px;">'
        f'<span style="width:12px;height:12px;border-radius:50%;'
        f'background:{c};display:inline-block"></span>{t}</span>'
        for t, c in couleurs.items()
    ])
    st.caption(f"🎨 Légende : {html}", unsafe_allow_html=True)


def _onglet_repartition(batiments: list[dict]):
    df = pd.DataFrame(batiments)

    col1, col2 = st.columns(2)

    with col1:
        # Répartition par type de bâtiment
        df_type = df.groupby("type").size().reset_index(name="count")
        fig = px.pie(
            df_type, values="count", names="type",
            title="Nombre de bâtiments par type",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Consommation totale par type
        df_conso = (
            df.groupby("type")["consommation"]
            .sum()
            .reset_index()
            .rename(columns={"consommation": "conso_kwh"})
        )
        fig2 = px.bar(
            df_conso, x="type", y="conso_kwh",
            title="Consommation totale par type (kWh)",
            color="type",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"conso_kwh": "kWh", "type": "Type"},
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Répartition par rôle (Producteur / Consommateur uniquement)
    df["role"] = df["production"].fillna(0).apply(
        lambda p: "Producteur" if p > 0 else "Consommateur"
    )
    df_role = df.groupby("role").size().reset_index(name="count")
    fig3 = px.bar(
        df_role, x="role", y="count",
        title="Nombre de bâtiments par rôle énergétique",
        color="role",
        color_discrete_map={
            "Consommateur": "#2563eb",
            "Producteur":   "#16a34a",
        },
        labels={"count": "Nombre", "role": "Rôle"},
    )
    st.plotly_chart(fig3, use_container_width=True)


def _onglet_producteurs(driver):
    st.markdown("**Top 20 bâtiments producteurs** (production annuelle décroissante)")

    try:
        producteurs = get_producers(driver)
        if not producteurs:
            st.info("Aucun producteur trouvé dans la base.")
            return

        df = pd.DataFrame(producteurs[:20])
        fig = px.bar(
            df,
            x="production",
            y="address",
            orientation="h",
            title="Top producteurs — production annuelle (kWh)",
            labels={"production": "kWh produits", "address": "Adresse"},
            color="production",
            color_continuous_scale="Greens",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur lors du chargement des producteurs : {e}")


def _onglet_profil_temporel(driver, batiments: list[dict]):
    st.markdown("**Profil temporel d'un bâtiment** (consommation et production par période 12h)")

    # Sélecteur de bâtiment
    options = {
        f"{b.get('address', b['building_id'])} ({b['building_id']})": b["building_id"]
        for b in batiments
    }
    choix = st.selectbox("Choisir un bâtiment", list(options.keys()))
    building_id = options[choix]

    try:
        periodes = get_energie_par_periode(driver, building_id)
        if not periodes:
            st.info("Pas de données temporelles pour ce bâtiment.")
            return

        df = pd.DataFrame(periodes)
        df["start_time"] = pd.to_datetime(df["start_time"])
        df = df.sort_values("start_time")

        fig = px.line(
            df,
            x="start_time",
            y=["kwh_consumed", "kwh_produced"],
            title=f"Profil énergétique — {choix}",
            labels={
                "start_time": "Période",
                "value": "kWh",
                "variable": "Flux",
            },
            color_discrete_map={
                "kwh_consumed": "#2563eb",
                "kwh_produced": "#16a34a",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

        # CO2
        if df["co2_cost"].notna().any():
            fig2 = px.line(
                df, x="start_time", y="co2_cost",
                title="Taux CO₂ (g/kWh)",
                labels={"start_time": "Période", "co2_cost": "g/kWh"},
                color_discrete_sequence=["#dc2626"],
            )
            st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur chargement profil temporel : {e}")


def _afficher_table(batiments: list[dict], driver):
    df = pd.DataFrame(batiments)

    df["role"]  = df["production"].fillna(0).apply(
        lambda p: "Producteur" if p > 0 else "Consommateur"
    )
    df["conso"] = df["consommation"].fillna(0).map(lambda x: f"{x:,.0f} kWh")
    df["prod"]  = df["production"].fillna(0).map(lambda x: f"{x:,.0f} kWh")

    colonnes = ["building_id", "address", "iris_name", "type", "role", "conso", "prod"]
    df_affiche = df[colonnes].rename(columns={
        "building_id": "ID",
        "address":     "Adresse",
        "iris_name":   "Zone IRIS",
        "type":        "Type",
        "role":        "Rôle",
        "conso":       "Consommation",
        "prod":        "Production",
    })

    # Recherche texte
    recherche = st.text_input("🔍 Filtrer par adresse ou zone IRIS", "")
    if recherche:
        masque = (
            df_affiche["Adresse"].str.contains(recherche, case=False, na=False) |
            df_affiche["Zone IRIS"].str.contains(recherche, case=False, na=False)
        )
        df_affiche = df_affiche[masque]

    st.dataframe(df_affiche, use_container_width=True, height=350)
    st.caption(f"{len(df_affiche)} bâtiments affichés")

    # Détail d'un bâtiment (contrat fournisseur)
    with st.expander("🔎 Voir le contrat d'un bâtiment"):
        bid = st.text_input("Entrer un building_id", "")
        if bid:
            contrat = get_contrat_batiment(driver, bid)
            if contrat:
                st.json(contrat)
            else:
                st.warning("Aucun contrat trouvé pour cet identifiant.")