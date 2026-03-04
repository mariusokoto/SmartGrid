# ─────────────────────────────────────────────
#  ui/page_optimisation.py  –  Lancement du pipeline
#  Neo4j → export → Julia → résultats
# ─────────────────────────────────────────────
import streamlit as st
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j_db.connector import get_driver
from data.exporter import preparer_input_julia, valider_output_julia
from julia.runner import julia_disponible, run_optimisation
from julia.mock_optimisation import run_mock_optimisation
from config import INPUT_PATH, OUTPUT_PATH


def render(params: dict):
    """
    Page 2 — Lancement de l'optimisation.
    params : dict retourné par render_sidebar()
    """

    st.title("⚙️ Optimisation des Smart Grids")
    st.caption("Sartrouville 2024")

    driver = get_driver()
    if driver is None:
        st.error("Impossible de se connecter à Neo4j.")
        return

    # ── Résumé des paramètres choisis ───────────
    st.subheader("📋 Paramètres sélectionnés")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Zone IRIS",         params["iris_name"])
    col2.metric("Membres minimum",   params["min_membres"])
    col3.metric("Rayon maximum",     f"{params['rayon_max']} m")
    col4.metric("Poids ratio local", f"{params['poids_local']:.0%}")

    col5, col6 = st.columns([1, 3])
    col5.metric("Prix opérateur", f"{params['prix_operateur']:.2f} €/kWh")

    st.divider()

    # ── Mode mock / réel ─────────────────────────
    st.subheader("🔍 Vérifications pré-lancement")

    mode_mock = st.toggle(
        "🧪 Mode simulation (sans Julia)",
        value=True,
        help=(
            "Activé  → simule l'optimisation en Python pour tester l'interface.\n"
            "Désactivé → lance le vrai optimisateur Julia (doit être installé)."
        ),
    )

    if mode_mock:
        st.info(
            "🧪 **Mode simulation activé** — les résultats sont générés aléatoirement "
            "à partir de tes vraies données Neo4j. Julia n'est pas requis."
        )
        neo4j_ok = driver is not None
        st.success("Neo4j connecté ✅") if neo4j_ok else st.error("Neo4j déconnecté ❌")
        if not neo4j_ok:
            st.stop()
    else:
        julia_ok = julia_disponible()
        if julia_ok:
            st.success("Julia détecté ✅")
        else:
            st.error(
                "Julia n'est pas détecté dans le PATH ❌\n\n"
                "Installe Julia depuis https://julialang.org/downloads/ "
                "puis relance l'application."
            )
        neo4j_ok = driver is not None
        st.success("Neo4j connecté ✅") if neo4j_ok else st.error("Neo4j déconnecté ❌")
        if not julia_ok or not neo4j_ok:
            st.stop()

    st.divider()

    # ── Étape 1 : Export Neo4j → JSON ───────────
    st.subheader("Étape 1 — Export Neo4j → JSON")

    if st.button("📤 Préparer les données", use_container_width=True):
        with st.spinner("Récupération des données depuis Neo4j..."):
            try:
                payload = preparer_input_julia(driver, params)
                st.session_state["payload"]     = payload
                st.session_state["export_ok"]   = True
                st.session_state["results"]      = None  # reset résultats précédents
            except Exception as e:
                st.error(f"Erreur lors de l'export : {e}")
                st.session_state["export_ok"] = False

    if st.session_state.get("export_ok"):
        payload = st.session_state["payload"]
        meta    = payload["meta"]

        st.success(
            f"✅ {meta['nb_batiments']} bâtiments et "
            f"{meta['nb_distances']} paires de distances exportés."
        )

        # Aperçu du JSON généré
        with st.expander("👁️ Aperçu du fichier input.json"):
            # Montre uniquement les 3 premiers bâtiments pour ne pas surcharger
            apercu = {
                **payload,
                "batiments": payload["batiments"][:3],
                "distances": payload["distances"][:5],
            }
            st.json(apercu)
            st.caption(f"Fichier complet : {os.path.abspath(INPUT_PATH)}")

    st.divider()

    # ── Étape 2 : Lancement Julia ────────────────
    st.subheader("Étape 2 — Optimisation Julia")

    if not st.session_state.get("export_ok"):
        st.info("Lance d'abord l'export (Étape 1).")
    else:
        timeout = st.number_input(
            "Timeout (secondes)",
            min_value=30,
            max_value=3600,
            value=300,
            step=30,
            help="Durée maximale accordée à Julia avant abandon.",
        )

        if st.button("🚀 Lancer l'optimisation", use_container_width=True, type="primary"):
            with st.spinner("Optimisation en cours..."):
                try:
                    if mode_mock:
                        results = run_mock_optimisation()
                    else:
                        results = run_optimisation(timeout=int(timeout))

                    # Validation de l'output
                    valide, message = valider_output_julia(results)
                    if not valide:
                        st.error(f"Output invalide : {message}")
                        st.session_state["results"] = None
                    else:
                        st.session_state["results"] = results
                        st.success(
                            f"✅ Optimisation terminée en "
                            f"{results.get('runtime_secondes', '?')}s "
                            f"({'simulation' if mode_mock else 'Julia'})"
                        )

                except TimeoutError as e:
                    st.error(f"⏱️ Timeout : {e}")
                except RuntimeError as e:
                    st.error(f"❌ Erreur Julia :\n{e}")
                    with st.expander("Voir les logs Julia"):
                        st.code(str(e))
                except Exception as e:
                    st.error(f"Erreur inattendue : {e}")

    # ── Résultats rapides ────────────────────────
    if st.session_state.get("results"):
        results = st.session_state["results"]
        st.divider()
        st.subheader("📊 Résultats rapides")

        grids = results.get("grids", [])
        non_assignes = results.get("batiments_non_assignes", [])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Grids formés",        len(grids))
        c2.metric("Non assignés",         len(non_assignes))

        if grids:
            ratio_moyen = sum(g["local_usage_ratio"] for g in grids) / len(grids)
            avantage_moyen = sum(g["prix_avantage"] for g in grids) / len(grids)
            c3.metric("Ratio local moyen",   f"{ratio_moyen:.1%}")
            c4.metric("Avantage prix moyen", f"{avantage_moyen:.3f} €/kWh")

        st.info("👉 Va sur la page **Résultats** pour voir la carte et l'analyse complète.")

    st.divider()

    # ── Étape 3 : Réimport dans Neo4j ───────────
    st.subheader("Étape 3 — Réimport des résultats dans Neo4j")

    if not st.session_state.get("results"):
        st.info("Lance d'abord l'optimisation (Étape 2).")
    else:
        st.warning(
            "⚠️ Cette étape va créer des nœuds :Grid et des relations :PART_OF "
            "dans Neo4j. Les grids existants seront mis à jour (MERGE)."
        )

        if st.button("📥 Réimporter dans Neo4j", use_container_width=True):
            with st.spinner("Réimport en cours..."):
                try:
                    from neo4j_db.queries import importer_resultats_grids
                    grids = st.session_state["results"]["grids"]
                    importer_resultats_grids(driver, grids)
                    st.success(
                        f"✅ {len(grids)} grids importés dans Neo4j "
                        f"avec leurs relations :PART_OF."
                    )
                except Exception as e:
                    st.error(f"Erreur lors du réimport : {e}")