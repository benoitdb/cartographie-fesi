"""Affichage de la fraîcheur des données (issue #47).

La source est republiée 5 fois par an en « annule et remplace ». Le pipeline
retenait déjà le bon millésime, mais rien à l'écran ne le disait : un utilisateur
pouvait conclure sur des montants vieux de plusieurs mois sans le savoir.

Ce qui se teste ici est la traduction de la date en libellé, et surtout son
refus de deviner : une date absente ou illisible ne doit produire aucun affichage
plutôt qu'un repli qui aurait l'air d'une information.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.millesime import libelle_millesime  # noqa: E402


def test_la_date_iso_devient_un_libelle_lisible():
    assert libelle_millesime({"millesime": "2026-03-16"}) == "export du 16/03/2026"


def test_une_date_absente_n_affiche_rien():
    """None fait taire l'affichage. Un « date inconnue » n'apprendrait rien et
    occuperait la place d'une information utile."""
    assert libelle_millesime({}) is None
    assert libelle_millesime({"millesime": None}) is None
    assert libelle_millesime(None) is None


def test_un_data_json_anterieur_a_la_fonctionnalite_reste_lisible():
    """Le champ n'existait pas avant : un `data.json` non régénéré ne doit pas
    faire échouer les pages."""
    assert libelle_millesime({"generated_at": "2026-08-01T10:00:00"}) is None


def test_une_date_illisible_n_affiche_rien_plutot_qu_une_date_fausse():
    assert libelle_millesime({"millesime": "16/03/2026"}) is None
    assert libelle_millesime({"millesime": "pas une date"}) is None
    assert libelle_millesime({"millesime": 20260316}) is None
