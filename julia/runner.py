# ─────────────────────────────────────────────
#  julia/runner.py  –  Appel Julia depuis Python
# ─────────────────────────────────────────────
import subprocess
import json
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import JULIA_SCRIPT, INPUT_PATH, OUTPUT_PATH


def julia_disponible() -> bool:
    """
    Vérifie que Julia est installé et accessible dans le PATH.
    """
    try:
        result = subprocess.run(
            ["julia", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_optimisation(timeout: int = 300) -> dict:
    """
    Lance le script Julia d'optimisation.

    Suppose que input.json est déjà écrit par exporter.py.
    Lit et retourne le contenu de output.json après exécution.

    timeout : secondes avant abandon (défaut 5 min)

    Retourne un dict avec les résultats ou lève une exception.
    """

    # Vérifie que l'input existe
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Fichier input introuvable : {INPUT_PATH}\n"
            "Lance d'abord preparer_input_julia()."
        )

    # Supprime un éventuel output précédent
    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)

    # Assure que le dossier output existe
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    debut = time.time()

    try:
        result = subprocess.run(
            ["julia", JULIA_SCRIPT, INPUT_PATH, OUTPUT_PATH],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Julia a dépassé le timeout de {timeout}s. "
            "Réduis le nombre de bâtiments ou augmente le timeout."
        )
    except FileNotFoundError:
        raise EnvironmentError(
            "Julia n'est pas trouvé dans le PATH. "
            "Installe Julia depuis https://julialang.org/downloads/"
        )

    duree = round(time.time() - debut, 2)

    # Vérifie le code de retour
    if result.returncode != 0:
        raise RuntimeError(
            f"Julia a terminé avec une erreur (code {result.returncode}).\n"
            f"stderr :\n{result.stderr}"
        )

    # Vérifie que l'output a bien été créé
    if not os.path.exists(OUTPUT_PATH):
        raise FileNotFoundError(
            f"Julia n'a pas produit de fichier output : {OUTPUT_PATH}\n"
            f"stdout Julia :\n{result.stdout}"
        )

    # Lit et parse l'output
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        output = json.load(f)

    # Ajoute le runtime mesuré côté Python (complète celui de Julia)
    output["runtime_python_secondes"] = duree

    return output


def get_julia_logs() -> tuple[str, str]:
    """
    Retourne (stdout, stderr) du dernier appel Julia.
    Utile pour déboguer depuis l'interface.
    """
    try:
        result = subprocess.run(
            ["julia", JULIA_SCRIPT, INPUT_PATH, OUTPUT_PATH],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.stdout, result.stderr
    except Exception as e:
        return "", str(e)