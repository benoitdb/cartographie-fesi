import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.filters import MAX_RECHERCHE_PROJET_CHARS, filtrer_liste_projets  # noqa: E402


def _projets():
    return pd.DataFrame(
        {
            "Intitulé du projet": ["Projet [pilote]", "Portail .*", "C++ pour tous"],
            "Nom du bénéficiaire": ["Association Alpha", "Métropole Beta", "Association Gamma"],
        }
    )


def test_la_recherche_est_litterale_dans_les_deux_colonnes():
    projets = _projets()

    assert filtrer_liste_projets(projets, "[pilote]")["Intitulé du projet"].tolist() == ["Projet [pilote]"]
    assert filtrer_liste_projets(projets, ".*")["Intitulé du projet"].tolist() == ["Portail .*"]
    assert filtrer_liste_projets(projets, "gamma")["Intitulé du projet"].tolist() == ["C++ pour tous"]


def test_la_recherche_est_bornee_a_200_caracteres():
    titre_borne = "P" * MAX_RECHERCHE_PROJET_CHARS
    projets = pd.DataFrame(
        {
            "Intitulé du projet": [titre_borne],
            "Nom du bénéficiaire": ["Association Delta"],
        }
    )
    recherche_trop_longue = titre_borne + "x"

    resultat = filtrer_liste_projets(projets, recherche_trop_longue)

    assert resultat["Intitulé du projet"].tolist() == [titre_borne]
