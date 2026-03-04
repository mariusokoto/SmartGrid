from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"

# On ne met plus d'utilisateur ni de mot de passe
driver = GraphDatabase.driver(URI, auth=None) 

def test_connexion():
    try:
        driver.verify_connectivity()
        print("Connexion réussie sans mot de passe !")
    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        driver.close()

test_connexion()