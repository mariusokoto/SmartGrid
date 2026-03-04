# ─────────────────────────────────────────────
#  ui/page_resultats.py  –  Résultats & analyse
#  Carte des grids + comparatif + statistiques
# ─────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j_db.connector import get_driver
from neo4j_db.queries import get_all_buildings, get_grids
from map.folium_map import carte_grids


def render(params: dict):
    """
    Page 3 — Résultats de l'optimisation.
    params : dict retourné par render_sidebar()
    """

    st.title("📊 Résultats — Smart Grids Sartrouville 2024")

    # ── Source des résultats ─────────────────────
    # Priorité : session_state (résultat frais) sinon Neo4j (résultats précédents)
    results  = st.session_state.get("results")
    grids    = _charger_grids(results)

    if not grids:
        st.info(
            "Aucun résultat disponible. "
            "Lance une optimisation depuis la page **Optimisation** "
            "ou réimporte des grids dans Neo4j."
        )
        return

    driver = get_driver()
    if driver is None:
        st.error("Impossible de se connecter à Neo4j.")
        return

    # Charge tous les bâtiments pour la carte
    with st.spinner("Chargement des bâtiments..."):
        batiments = get_all_buildings(driver)

    # ── KPIs globaux ─────────────────────────────
    st.subheader("📈 Vue d'ensemble")
    _afficher_kpis_globaux(grids, batiments, results)
    st.divider()

    # ── Carte des grids ──────────────────────────
    st.subheader("🗺️ Carte des grids")
    carte = carte_grids(batiments, grids)
    st_folium(carte, width="100%", height=550, returned_objects=[])
    st.divider()

    # ── Analyses ─────────────────────────────────
    st.subheader("🔬 Analyse détaillée")
    tab1, tab2, tab3, tab4 = st.tabs([
        "Comparatif grids",
        "Ratio local",
        "Avantage prix",
        "Membres & tailles",
    ])

    with tab1:
        _onglet_comparatif(grids)

    with tab2:
        _onglet_ratio_local(grids)

    with tab3:
        _onglet_avantage_prix(grids, params)

    with tab4:
        _onglet_membres(grids, batiments)

    st.divider()

    # ── Inspection d'un grid ─────────────────────
    st.subheader("🔍 Inspecter un grid")
    _inspecter_grid(grids, batiments)

    st.divider()

    # ── Table des grids ──────────────────────────
    st.subheader("📋 Table des grids")
    _afficher_table_grids(grids)

    # ── Bâtiments non assignés ───────────────────
    if results and results.get("batiments_non_assignes"):
        st.subheader("⚠️ Bâtiments non assignés")
        _afficher_non_assignes(results["batiments_non_assignes"], batiments)

    # ── Runtime ──────────────────────────────────
    if results:
        st.divider()
        st.caption(
            f"⏱️ Runtime Julia : {results.get('runtime_secondes', '?')}s | "
            f"Python : {results.get('runtime_python_secondes', '?')}s"
        )


# ══════════════════════════════════════════════
#  CHARGEMENT DES GRIDS
# ══════════════════════════════════════════════

def _charger_grids(results) -> list[dict]:
    """
    Charge les grids depuis session_state ou Neo4j.
    """
    # Depuis session_state (résultat frais de Julia)
    if results and results.get("grids"):
        return results["grids"]

    # Depuis Neo4j (résultats d'une session précédente)
    try:
        driver = get_driver()
        if driver:
            grids_neo4j = get_grids(driver)
            if grids_neo4j:
                # Adapte le format Neo4j au format Julia
                return [
                    {
                        "grid_id"           : g["grid_id"],
                        "membres"           : g["membres"],
                        "local_usage_ratio" : g.get("local_usage_ratio", 0.0),
                        "prix_avantage"     : g.get("prix_avantage", 0.0),
                        "rayon_effectif"    : g.get("radius", 0),
                    }
                    for g in grids_neo4j
                ]
    except Exception:
        pass

    return []


# ══════════════════════════════════════════════
#  BLOCS INTERNES
# ══════════════════════════════════════════════

def _afficher_kpis_globaux(grids, batiments, results):
    nb_grids         = len(grids)
    total_membres    = sum(len(g["membres"]) for g in grids)
    ratio_moyen      = sum(g["local_usage_ratio"] for g in grids) / nb_grids if nb_grids else 0
    avantage_moyen   = sum(g["prix_avantage"] for g in grids) / nb_grids if nb_grids else 0
    taille_moy       = total_membres / nb_grids if nb_grids else 0
    non_assignes     = len(results.get("batiments_non_assignes", [])) if results else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Grids formés",         nb_grids)
    c2.metric("Bâtiments couverts",   total_membres)
    c3.metric("Non assignés",         non_assignes)
    c4.metric("Taille moyenne",       f"{taille_moy:.1f}")
    c5.metric("Ratio local moyen",    f"{ratio_moyen:.1%}")
    c6.metric("Avantage prix moyen",  f"{avantage_moyen:.3f} €/kWh")


def _onglet_comparatif(grids: list[dict]):
    """Tableau de bord comparatif de tous les grids."""
    df = pd.DataFrame([
        {
            "Grid"             : f"Grid {g['grid_id']}",
            "Membres"          : len(g["membres"]),
            "Rayon (m)"        : g["rayon_effectif"],
            "Ratio local"      : g["local_usage_ratio"],
            "Avantage prix"    : g["prix_avantage"],
        }
        for g in grids
    ])

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Ratio local",
        x=df["Grid"],
        y=df["Ratio local"],
        marker_color="#2563eb",
        yaxis="y1",
    ))
    fig.add_trace(go.Bar(
        name="Avantage prix (€/kWh)",
        x=df["Grid"],
        y=df["Avantage prix"],
        marker_color="#16a34a",
        yaxis="y2",
    ))

    fig.update_layout(
        title="Comparatif des grids — ratio local vs avantage prix",
        barmode="group",
        yaxis=dict(title="Ratio local (0→1)", tickformat=".0%"),
        yaxis2=dict(title="Avantage prix (€/kWh)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _onglet_ratio_local(grids: list[dict]):
    """Analyse du ratio de consommation locale."""
    df = pd.DataFrame([
        {
            "Grid"        : f"Grid {g['grid_id']}",
            "Ratio local" : g["local_usage_ratio"],
            "Membres"     : len(g["membres"]),
        }
        for g in grids
    ]).sort_values("Ratio local", ascending=False)

    fig = px.bar(
        df,
        x="Grid",
        y="Ratio local",
        color="Ratio local",
        color_continuous_scale="Blues",
        title="Ratio local par grid (production locale / consommation locale)",
        labels={"Ratio local": "Ratio"},
        text=df["Ratio local"].map(lambda x: f"{x:.1%}"),
    )
    fig.update_traces(textposition="outside")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.1])
    st.plotly_chart(fig, use_container_width=True)

    # Interprétation
    bon    = sum(1 for g in grids if g["local_usage_ratio"] >= 0.7)
    moyen  = sum(1 for g in grids if 0.4 <= g["local_usage_ratio"] < 0.7)
    faible = sum(1 for g in grids if g["local_usage_ratio"] < 0.4)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Bon (≥70%)",    bon,    help="Production couvre au moins 70% de la conso locale")
    c2.metric("🟡 Moyen (40–70%)", moyen,  help="Production couvre 40 à 70% de la conso locale")
    c3.metric("🔴 Faible (<40%)",  faible, help="Production couvre moins de 40% de la conso locale")


def _onglet_avantage_prix(grids: list[dict], params: dict):
    """Analyse de l'avantage prix vs opérateur."""
    df = pd.DataFrame([
        {
            "Grid"           : f"Grid {g['grid_id']}",
            "Avantage prix"  : g["prix_avantage"],
            "Membres"        : len(g["membres"]),
        }
        for g in grids
    ]).sort_values("Avantage prix", ascending=False)

    fig = px.bar(
        df,
        x="Grid",
        y="Avantage prix",
        color="Avantage prix",
        color_continuous_scale="Greens",
        title=f"Avantage prix vs opérateur ({params['prix_operateur']:.2f} €/kWh)",
        labels={"Avantage prix": "€/kWh"},
        text=df["Avantage prix"].map(lambda x: f"{x:.3f}€"),
    )
    fig.update_traces(textposition="outside")
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="red",
        annotation_text="Seuil rentabilité",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Économie annuelle estimée
    st.markdown("**Économie annuelle estimée par grid**")
    rows = []
    for g in grids:
        bat_membres = [b for b in [] if b.get("building_id") in g["membres"]]
        rows.append({
            "Grid"              : f"Grid {g['grid_id']}",
            "Avantage (€/kWh)"  : f"{g['prix_avantage']:.4f}",
            "Membres"           : len(g["membres"]),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _onglet_membres(grids: list[dict], batiments: list[dict]):
    """Taille et composition des grids."""
    bat_index = {b["building_id"]: b for b in batiments}

    col1, col2 = st.columns(2)

    with col1:
        # Distribution des tailles
        tailles = [len(g["membres"]) for g in grids]
        fig = px.histogram(
            x=tailles,
            nbins=max(1, max(tailles) - min(tailles) + 1),
            title="Distribution des tailles de grids",
            labels={"x": "Nombre de membres", "y": "Nombre de grids"},
            color_discrete_sequence=["#2563eb"],
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Rayon effectif
        df_rayon = pd.DataFrame([
            {"Grid": f"Grid {g['grid_id']}", "Rayon (m)": g["rayon_effectif"]}
            for g in grids
        ])
        fig2 = px.bar(
            df_rayon, x="Grid", y="Rayon (m)",
            title="Rayon effectif par grid",
            color="Rayon (m)",
            color_continuous_scale="Oranges",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Composition par type de bâtiment
    st.markdown("**Composition par type de bâtiment**")
    rows = []
    for g in grids:
        types = {}
        for bat_id in g["membres"]:
            b = bat_index.get(bat_id, {})
            t = b.get("type", "Inconnu")
            types[t] = types.get(t, 0) + 1
        rows.append({
            "Grid"        : f"Grid {g['grid_id']}",
            "Total"       : len(g["membres"]),
            **types,
        })

    df_comp = pd.DataFrame(rows).fillna(0)
    st.dataframe(df_comp, use_container_width=True)


def _afficher_table_grids(grids: list[dict]):
    df = pd.DataFrame([
        {
            "Grid ID"          : g["grid_id"],
            "Membres"          : len(g["membres"]),
            "Rayon (m)"        : g["rayon_effectif"],
            "Ratio local"      : f"{g['local_usage_ratio']:.1%}",
            "Avantage prix"    : f"{g['prix_avantage']:.4f} €/kWh",
            "IDs membres"      : ", ".join(str(m) for m in g["membres"][:5])
                                 + ("..." if len(g["membres"]) > 5 else ""),
        }
        for g in grids
    ])
    st.dataframe(df, use_container_width=True)

    # Export CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Télécharger les résultats (CSV)",
        data=csv,
        file_name="grids_sartrouville_2024.csv",
        mime="text/csv",
    )


def _inspecter_grid(grids: list[dict], batiments: list[dict]):
    """
    Sélecteur de grid → carte zoomée + table des membres.
    """
    if not grids:
        st.info("Aucun grid disponible.")
        return

    bat_index = {b["building_id"]: b for b in batiments}

    # Sélecteur
    ids_grids = [g["grid_id"] for g in grids]
    grid_id_choisi = st.selectbox(
        "Choisir un grid",
        options=ids_grids,
        format_func=lambda gid: (
            f"Grid {gid} — "
            f"{len(next(g for g in grids if g['grid_id'] == gid)['membres'])} membres"
        ),
    )

    grid = next(g for g in grids if g["grid_id"] == grid_id_choisi)
    membres_ids = grid["membres"]
    membres = [bat_index[m] for m in membres_ids if m in bat_index]

    if not membres:
        st.warning("Aucun bâtiment trouvé pour ce grid.")
        return

    # ── Métriques du grid ────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Membres",         len(membres))
    c2.metric("Rayon effectif",  f"{grid['rayon_effectif']} m")
    c3.metric("Ratio local",     f"{grid['local_usage_ratio']:.1%}")
    c4.metric("Avantage prix",   f"{grid['prix_avantage']:.4f} €/kWh")

    # ── Carte zoomée ─────────────────────────────
    st.markdown("**Carte des membres**")
    carte = _carte_grid_zoom(grid, membres)
    st_folium(carte, width="100%", height=480, returned_objects=[])

    # ── Table des membres ────────────────────────
    st.markdown("**Membres du grid**")
    rows = []
    for b in membres:
        conso = b.get("consommation") or 0
        prod  = b.get("production") or 0
        rows.append({
            "ID"           : b["building_id"],
            "Adresse"      : b.get("address", "?"),
            "Zone IRIS"    : b.get("iris_name", "?"),
            "Type"         : b.get("type", "?"),
            "Rôle"         : "☀️ Producteur" if prod > 0 else "🔋 Consommateur",
            "Conso (kWh)"  : f"{conso:,.0f}",
            "Prod (kWh)"   : f"{prod:,.0f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=300)

    # Bilan énergétique du grid
    conso_tot = sum(b.get("consommation") or 0 for b in membres)
    prod_tot  = sum(b.get("production") or 0 for b in membres)
    ratio     = prod_tot / conso_tot if conso_tot > 0 else 0

    st.markdown(
        f"**Bilan énergétique du grid {grid_id_choisi} :** "
        f"Conso totale `{conso_tot:,.0f} kWh` | "
        f"Prod totale `{prod_tot:,.0f} kWh` | "
        f"Ratio `{ratio:.2%}`"
    )


def _carte_grid_zoom(grid: dict, membres: list[dict]) -> object:
    """
    Carte Folium zoomée sur les membres d'un seul grid.
    Markers détaillés + lignes reliant les membres + cercle de rayon.
    """
    import folium

    lats = [b["lat"] for b in membres if b.get("lat")]
    lons = [b["lon"] for b in membres if b.get("lon")]

    if not lats:
        return folium.Map(location=[48.9372, 2.1628], zoom_start=14)

    lat_c = sum(lats) / len(lats)
    lon_c = sum(lons) / len(lons)

    carte = folium.Map(location=[lat_c, lon_c], zoom_start=16)

    couleur_grid = "#2563eb"

    # Cercle de rayon effectif
    folium.Circle(
        location=[lat_c, lon_c],
        radius=grid["rayon_effectif"],
        color=couleur_grid,
        fill=True,
        fill_opacity=0.06,
        tooltip=f"Rayon effectif : {grid['rayon_effectif']} m",
    ).add_to(carte)

    # Marker centroïde
    folium.Marker(
        location=[lat_c, lon_c],
        icon=folium.DivIcon(html=f"""
            <div style="background:{couleur_grid};color:white;border-radius:50%;
                        width:28px;height:28px;display:flex;align-items:center;
                        justify-content:center;font-weight:bold;font-size:12px;
                        box-shadow:0 2px 4px rgba(0,0,0,0.3)">
                {grid['grid_id']}
            </div>
        """),
        tooltip=f"Centroïde Grid {grid['grid_id']}",
    ).add_to(carte)

    # Markers membres
    for b in membres:
        if not b.get("lat") or not b.get("lon"):
            continue

        prod     = b.get("production") or 0
        conso    = b.get("consommation") or 0
        est_prod = prod > 0
        couleur  = "#16a34a" if est_prod else "#2563eb"
        icone    = "☀️" if est_prod else "🔋"

        popup_html = f"""
        <div style="font-family:sans-serif;font-size:13px;min-width:200px">
            <b>{b.get('address', b['building_id'])}</b><br>
            <span style="color:#6b7280">{b.get('iris_name', '')} — {b.get('type', '')}</span><br><br>
            {icone} {'Producteur' if est_prod else 'Consommateur'}<br>
            🔋 Conso : <b>{conso:,.0f} kWh</b><br>
            ☀️ Prod  : <b>{prod:,.0f} kWh</b><br>
            📍 <code style="font-size:11px">{b['building_id']}</code>
        </div>
        """

        folium.CircleMarker(
            location=[b["lat"], b["lon"]],
            radius=9,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=b.get("address", b["building_id"]),
        ).add_to(carte)

        # Ligne du membre vers le centroïde
        folium.PolyLine(
            locations=[[b["lat"], b["lon"]], [lat_c, lon_c]],
            color=couleur_grid,
            weight=1.5,
            opacity=0.4,
            dash_array="5",
        ).add_to(carte)

    # Légende rapide
    legende = f"""
    <div style="position:fixed;bottom:20px;left:20px;z-index:1000;
                background:white;padding:10px 14px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2);font-family:sans-serif;font-size:13px">
        <b>Grid {grid['grid_id']}</b> — {len(membres)} membres<br>
        <span style="color:#16a34a">● Producteur</span> &nbsp;
        <span style="color:#2563eb">● Consommateur</span>
    </div>
    """
    carte.get_root().html.add_child(folium.Element(legende))

    return carte


def _afficher_non_assignes(ids_non_assignes: list, batiments: list[dict]):
    bat_index = {b["building_id"]: b for b in batiments}
    rows = []
    for bat_id in ids_non_assignes:
        b = bat_index.get(bat_id, {})
        rows.append({
            "building_id" : bat_id,
            "Adresse"     : b.get("address", "?"),
            "Zone IRIS"   : b.get("iris_name", "?"),
            "Type"        : b.get("type", "?"),
            "Conso (kWh)" : b.get("consommation", 0),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.caption(
        f"{len(ids_non_assignes)} bâtiments non assignés — "
        "trop isolés ou ne respectant pas les contraintes de membres minimum."
    )