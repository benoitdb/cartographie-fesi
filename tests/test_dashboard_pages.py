"""Tests de fumée du dashboard : chaque page se rend-elle sans exception ?

Ce qu'ils attrapent, et qui n'était couvert par rien jusqu'ici : import cassé,
colonne renommée dans le pipeline mais pas dans l'affichage, fichier de données
manquant, régression d'API Streamlit ou Plotly. Autrement dit la classe d'erreurs
la plus probable sur ~3 000 lignes de `dashboard/` sans aucun test.

Ce qu'ils ne prouvent PAS : que les chiffres affichés sont justes. La fixture
n'est pas auto-cohérente (voir tests/fixtures/README.md) et aucune valeur n'est
comparée ici. C'est le rôle des tests de la couche de calcul
(`test_stats_calculs.py`, `test_cofinancement_regles.py`,
`test_pilotage_calculs.py`), qui n'affichent rien mais vérifient des valeurs.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DASHBOARD = RACINE / "dashboard"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dashboard"

# `dashboard/` doit être sur le sys.path : ses modules s'importent en `utils.*`,
# comme quand streamlit est lancé depuis ce dossier.
sys.path.insert(0, str(DASHBOARD))

pytest.importorskip("streamlit", reason="dépendances du dashboard non installées")

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = [
    DASHBOARD / "Accueil.py",
    *sorted((DASHBOARD / "pages").glob("*.py")),
]


@pytest.fixture
def donnees_fixture(monkeypatch):
    """Fait lire au dashboard l'échantillon committé plutôt que `data/processed/`,
    qui est gitignoré et donc absent d'un clone nu."""
    import streamlit as st

    from utils import data_loader

    monkeypatch.setattr(data_loader, "DATA_PATH", FIXTURE / "data.json")
    monkeypatch.setattr(
        data_loader, "BENEFICIAIRES_FUZZY_PATH", FIXTURE / "beneficiaires_fuzzy.json"
    )
    monkeypatch.setattr(
        data_loader,
        "TRANSFERTS_SOLIDARITE_PATH",
        FIXTURE / "transferts_solidarite.json",
    )
    # Sans cela, la première page rendue mettrait ses données en cache et les
    # suivantes les réutiliseraient : le monkeypatch n'aurait plus aucun effet.
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_se_rend_sans_exception(page, donnees_fixture):
    at = AppTest.from_file(str(page), default_timeout=120).run()
    assert not at.exception, (
        f"{page.name} a levé : {at.exception[0].value if at.exception else ''}"
    )


def test_la_fixture_est_bien_la_source_lue(donnees_fixture):
    """Sans ce test, la suite passerait aussi bien en lisant `data/processed/`,
    présent sur le poste de développement mais absent en CI : elle serait verte
    ici et rouge là-bas, ou pire, verte des deux côtés pour deux raisons
    différentes. On vérifie donc que ce sont bien les 400 opérations de
    l'échantillon qui arrivent jusqu'au chargeur."""
    from utils.data_loader import load_data

    assert len(load_data()["operations"]) == 400


def test_les_quatre_pages_sont_couvertes():
    """Garde-fou sur le garde-fou : une page ajoutée dans `pages/` sans test
    passerait autrement inaperçue, et la suite resterait verte en ne couvrant
    plus tout le dashboard."""
    assert len(PAGES) == 4, f"pages trouvées : {[p.name for p in PAGES]}"
