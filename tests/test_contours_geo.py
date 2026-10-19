"""Contours géographiques (`data/geo/`, #198) : chaque chemin lu par le dashboard
et le dossier servi à la stack Metabase désignent des fichiers présents et lisibles.

Ces fichiers ont déménagé de `frontend/public/geo/` quand le prototype React a été
retiré. Un chemin oublié ne lève rien à l'import : la carte casse à l'affichage,
sur la seule page qui la dessine. Ce test le voit sur un clone nu, sans rendu.
"""

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils import data_loader, departments  # noqa: E402

CHEMINS_DASHBOARD = {
    "GEOJSON_PATH": data_loader.GEOJSON_PATH,
    "GEOJSON_DROMCOM_PATH": data_loader.GEOJSON_DROMCOM_PATH,
    "DROMCOM_CODES_POSTAUX_PATH": data_loader.DROMCOM_CODES_POSTAUX_PATH,
    "DEPARTEMENTS_GEOJSON_PATH": departments.DEPARTEMENTS_GEOJSON_PATH,
}


def test_chaque_chemin_du_dashboard_designe_un_json_lisible():
    for nom, chemin in CHEMINS_DASHBOARD.items():
        assert chemin.is_file(), f"{nom} pointe vers un fichier absent : {chemin}"
        json.loads(chemin.read_text(encoding="utf-8"))


def test_les_geojson_du_dashboard_portent_des_contours():
    for nom, chemin in CHEMINS_DASHBOARD.items():
        if chemin.suffix != ".geojson":
            continue
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        assert contenu.get("type") == "FeatureCollection", nom
        assert contenu["features"], f"{nom} ne contient aucun contour"


def test_le_serveur_geojson_de_metabase_monte_le_dossier_des_contours():
    # Lu sans YAML (absent de l'environnement de test) : le montage du service
    # `geojson` est la seule ligne du compose qui monte un dossier sur `/geo`.
    compose = (RACINE / "metabase" / "docker-compose.yml").read_text()
    montages = re.findall(r"^\s*-\s*(\S+):/geo(?::ro)?\s*$", compose, flags=re.MULTILINE)
    assert len(montages) == 1, montages
    dossier = (RACINE / "metabase" / montages[0]).resolve()
    assert dossier == (RACINE / "data" / "geo").resolve(), montages[0]
    assert dossier.is_dir(), f"montage vers un dossier absent : {dossier}"
