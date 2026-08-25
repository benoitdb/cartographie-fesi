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

# La page « Validation de la source » ne lit pas `data.json` : elle profile
# d'autres fichiers (2014-2020…) et affiche la fraîcheur de *chaque source* dans
# son corps, pas le millésime de l'export 2021-2027 en pied de sidebar. Elle est
# donc hors du test de fraîcheur ci-dessous, qui vaut pour les pages d'analyse.
PAGES_AVEC_MILLESIME = [p for p in PAGES if p.stem != "4_Validation_source"]

# Le millésime affiché **suit la période de la page** (issue #83) : l'espace
# 2014-2020 lit son propre fichier, dont la date déclarée est celle de
# l'extraction Synergie. Une page qui afficherait la date de l'autre période
# serait le pire des cas — des chiffres justes sous une date fausse.
MILLESIME_PAR_DEFAUT = "export du 16/03/2026"
MILLESIME_ATTENDU = {"5_Période_2014-2020": "export du 30/08/2023"}


@pytest.fixture
def donnees_fixture(monkeypatch):
    """Fait lire au dashboard l'échantillon committé plutôt que `data/processed/`,
    qui est gitignoré et donc absent d'un clone nu."""
    import streamlit as st

    from utils import data_loader

    monkeypatch.setattr(data_loader, "DATA_PATH", FIXTURE / "data.json")
    monkeypatch.setattr(data_loader, "DATA_2014_2020_PATH", FIXTURE / "data_2014-2020.json")
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
    différentes. On vérifie donc que c'est bien l'échantillon qui arrive jusqu'au
    chargeur — le champ `metadata.fixture` n'existe que dans celui-ci."""
    from utils.data_loader import load_data

    data = load_data()
    assert data["metadata"].get("fixture")
    assert len(data["operations"]) == data["metadata"]["total_operations"] == 413


def test_la_fixture_est_auto_coherente(donnees_fixture):
    """Ses agrégats décrivent son propre échantillon, plus le jeu complet
    (issue #60) : chaque opération compte dans exactement une partition, et les
    totaux par fonds couvrent tout le périmètre. C'est ce qui autorise désormais
    une assertion sur une valeur lue depuis la fixture."""
    from utils.data_loader import load_data

    data = load_data()
    agregats = data["aggregates"]

    par_partition = (
        sum(v["count"] for v in agregats["by_region"].values())
        + agregats["national"]["count"]
        + agregats["interregional"]["count"]
    )
    assert par_partition == len(data["operations"])

    montant_total = sum(op["Montant UE"] for op in data["operations"] if op["Montant UE"])
    montant_par_fonds = sum(v["montant_ue_total"] for v in agregats["by_fonds"].values())
    assert montant_par_fonds == pytest.approx(montant_total)


def test_toutes_les_pages_sont_couvertes():
    """Garde-fou sur le garde-fou : une page ajoutée dans `pages/` sans test
    passerait autrement inaperçue, et la suite resterait verte en ne couvrant
    plus tout le dashboard."""
    assert len(PAGES) == 6, f"pages trouvées : {[p.name for p in PAGES]}"


@pytest.mark.parametrize("page", PAGES_AVEC_MILLESIME, ids=lambda p: p.stem)
def test_la_fraicheur_des_donnees_est_affichee(page, donnees_fixture):
    """La source est republiée 5 fois par an : la date de l'export doit être
    lisible sur **chaque** page, pas seulement sur celle où on a pensé à
    l'ajouter (issue #47). Ce test échoue si une page nouvelle oublie l'appel."""
    at = AppTest.from_file(str(page), default_timeout=120).run()
    attendu = MILLESIME_ATTENDU.get(page.stem, MILLESIME_PAR_DEFAUT)

    assert any(attendu in c.value for c in at.sidebar.caption), (
        f"{page.name} n'affiche pas le millésime attendu ({attendu})"
    )
