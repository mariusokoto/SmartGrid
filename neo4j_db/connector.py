# ─────────────────────────────────────────────
#  neo4j/connector.py  –  Connexion à Neo4j
# ─────────────────────────────────────────────
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD


@st.cache_resource
def get_driver():
    """
    Crée et retourne le driver Neo4j.
    Mis en cache par Streamlit → une seule connexion pour toute la session.
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except ServiceUnavailable:
        st.error("❌ Neo4j est inaccessible. Vérifie que la base est démarrée dans Neo4j Desktop.")
        return None
    except AuthError:
        st.error("❌ Identifiants Neo4j incorrects. Vérifie NEO4J_USER et NEO4J_PASSWORD dans config.py.")
        return None



def test_connexion() -> bool:
    """
    Teste la connexion, retourne True/False.
    Utilisé pour afficher le statut dans la sidebar.
    """
    driver = get_driver()
    if driver is None:
        return False
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return True
    except Exception:
        return False