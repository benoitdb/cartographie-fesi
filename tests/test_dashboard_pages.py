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
        data_loader, "DATA_2014_2020_NORMANDIE_PATH", FIXTURE / "data_2014-2020_normandie.json"
    )
    monkeypatch.setattr(
        data_loader,
        "DATA_2014_2020_NOUVELLE_AQUITAINE_PATH",
        FIXTURE / "data_2014-2020_nouvelle_aquitaine.json",
    )
    monkeypatch.setattr(
        data_loader, "DATA_2014_2020_BRETAGNE_PATH", FIXTURE / "data_2014-2020_bretagne_officiel.json"
    )
    monkeypatch.setattr(
        data_loader, "DATA_2014_2020_PON_FSE_PATH", FIXTURE / "data_2014-2020_pon_fse.json"
    )
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


# --- Onglet Pilotage de l'espace 2014-2020 (issue #93) ------------------------

PAGE_2014_2020 = DASHBOARD / "pages" / "5_Période_2014-2020.py"


def _rendre_perimetre_2014_2020(perimetre):
    """Rend la page 2014-2020 sur un périmètre donné, avec une instance neuve.

    Une instance neuve par périmètre, jamais réutilisée d'un appel à l'autre : un
    `AppTest` rejoué sur plusieurs valeurs successives lève des `KeyError` sur les clés
    de widget des fragments, artefact du harnais et non bug de la page (constaté sur la
    Vue Régionale)."""
    at = AppTest.from_file(str(PAGE_2014_2020), default_timeout=120).run()
    at.selectbox(key="perimetre_2014_2020").set_value(perimetre).run()
    assert not at.exception, f"{perimetre} a levé : {at.exception[0].value if at.exception else ''}"
    return at


def test_pilotage_affiche_sur_une_region_couverte_par_synergie(donnees_fixture):
    """Le chemin qui rend réellement le bloc de pilotage. Le test de fumée général ne
    l'exerce pas : la page s'ouvre sur « Ensemble national », justement l'un des
    périmètres où le pilotage est masqué."""
    at = _rendre_perimetre_2014_2020("Corse")
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" in textes
    # La provenance des enveloppes doit accompagner le taux, jamais être décrochée.
    captions = " ".join(el.value for el in at.caption)
    assert "Accord de partenariat 2014-2020" in captions
    assert "REACT-EU" in captions


def test_pilotage_affiche_sur_ensemble_national(donnees_fixture):
    """N'est plus masqué depuis la fusion complète des six sources
    (`fusionner_ensemble_national_2014_2020`, arbitrage Phase 4, issue #121) : les trois
    régions hors-Synergie (Normandie, Nouvelle-Aquitaine, Bretagne) et le PON FSE y sont
    désormais fusionnés, comme sur leur propre périmètre — c'était la seule pièce qui
    manquait à un engagé complet ici, exactement comme pour Volet national (#95, point 3)."""
    at = _rendre_perimetre_2014_2020("Ensemble national")
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" in textes
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" not in infos
    assert "Aucun des fonds sélectionnés" not in infos

    # La fusion doit se voir dans le tableau "Programmes" de la Vue d'ensemble : un
    # programme propre à Bretagne (fichier régional, la fixture Synergie ne la couvre
    # qu'à la marge, #68) ET un programme PON FSE routé au national (Programme
    # Opérationnel National FSE) doivent tous deux y figurer — la table resterait
    # Synergie seule si la fusion n'était pas branchée sur `ops_perimetre`.
    programmes = _programmes_affiches(at)
    assert "Programme Opérationnel National FSE" in programmes
    assert "Programme opérationnel Bretagne FEDER 2014-2020" in programmes


def _programmes_affiches(at):
    """La table « Programmes » de l'onglet Vue d'ensemble : présente sur tout périmètre,
    à un index qui varie (Ensemble national affiche un tableau de classement des régions
    juste avant). Sélectionnée par ses colonnes plutôt que par position."""
    for df in at.dataframe:
        if "Libellé Programme" in df.value.columns:
            return set(df.value["Libellé Programme"])
    raise AssertionError("Aucune table « Programmes » sur cette page")


def test_pilotage_affiche_sur_volet_national_avec_pon_fse(donnees_fixture):
    """Volet national n'est plus masqué depuis que PON FSE et PO IEJ national y sont
    fusionnés (issue #95, point 3) : c'était la seule pièce qui manquait à un engagé
    complet sur ce périmètre. Vérifie aussi que la clé d'enveloppe "national" (pas le
    libellé "Volet national") est bien celle utilisée pour le rapprochement — un
    mauvais mapping renverrait un dict vide et retomberait sur le message "aucune
    enveloppe programmée" plutôt que sur un vrai taux."""
    at = _rendre_perimetre_2014_2020("Volet national")
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" in textes
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" not in infos
    assert "Aucun des fonds sélectionnés" not in infos
    captions = " ".join(el.value for el in at.caption)
    assert "programme opérationnel national FSE" in captions

    # PON FSE est là, mais aucun des cinq PO DROM : ce sont eux qui doivent ventiler vers
    # leur région, pas rejoindre ce périmètre agrégé (#95). Pas d'assertion sur le PO IEJ
    # national : la fixture Synergie, stratifiée par région et non par fonds, ne contient
    # par hasard aucune opération IEJ — son fonds n'apparaît donc pas dans le filtre Fonds
    # de la page, et ses opérations PON FSE en sont écartées avec lui (comportement
    # attendu du filtre, pas un défaut de routage — voir test_regions_pon_fse_route_les_
    # sept_programmes dans test_periodes.py pour la couverture du PO IEJ national).
    programmes = _programmes_affiches(at)
    assert "Programme Opérationnel National FSE" in programmes
    assert not programmes & {"PO réunion", "PO Guadeloupe", "PO Martinique", "PO Guyane", "PO Mayotte"}


@pytest.mark.parametrize(
    ("perimetre", "libelle_po"),
    [
        ("La Réunion", "PO réunion"),
        ("Guadeloupe", "PO Guadeloupe"),
        ("Martinique", "PO Martinique"),
        ("Guyane", "PO Guyane"),
        ("Mayotte", "PO Mayotte"),
    ],
)
def test_pilotage_drom_fusionne_le_fse_du_pon(perimetre, libelle_po, donnees_fixture):
    """Les cinq PO FSE État des DROM (issue #95, point 3) sont fusionnés à l'engagé
    Synergie de leur région, pas remplacés par lui : leur FSE d'État, absent ou
    marginal côté Synergie, doit désormais compter dans le taux affiché — et seul le
    PO de cette région doit apparaître, jamais celui d'une autre (routage par
    `Libellé Programme`, pas par la seule région de chaque opération)."""
    at = _rendre_perimetre_2014_2020(perimetre)
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" in textes
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" not in infos
    assert "second fichier" in infos

    programmes = _programmes_affiches(at)
    assert libelle_po in programmes
    autres_po_drom = {"PO réunion", "PO Guadeloupe", "PO Martinique", "PO Guyane", "PO Mayotte"} - {libelle_po}
    assert not programmes & autres_po_drom
    assert "Programme Opérationnel National FSE" not in programmes
    assert "Programme Opérationnel IEJ" not in programmes


@pytest.mark.parametrize("perimetre", ["Normandie", "Nouvelle-Aquitaine", "Bretagne"])
def test_pilotage_affiche_sur_les_perimetres_avec_fichier_regional(perimetre, donnees_fixture):
    """Depuis #95, ces trois périmètres sont pilotés depuis leur propre fichier régional
    (fixture committée ici) plutôt que masqués : c'est le changement de comportement que
    cette issue livre. Normandie, en particulier, était même absente du sélecteur avant
    #95 (absente de `aggregates.by_region` de Synergie) ; Bretagne l'a rejoint depuis
    l'export officiel data.bretagne.bzh."""
    at = _rendre_perimetre_2014_2020(perimetre)
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" in textes
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" not in infos


def test_bretagne_fse_signale_sa_granularite(donnees_fixture):
    """Le FSE breton dépasse son enveloppe (111 %) sans être une surconsommation : sept
    marchés de formation agrégés, pas des opérations unitaires (#95, point 2). La mention
    doit accompagner le taux plutôt que le laisser se lire comme un vrai dépassement."""
    at = _rendre_perimetre_2014_2020("Bretagne")
    captions = " ".join(el.value for el in at.caption)
    assert "Le FSE breton dépasse son enveloppe" in captions


def test_normandie_disparait_du_selecteur_si_son_fichier_est_absent(donnees_fixture, monkeypatch):
    """Normandie n'a **aucune** présence dans les agrégats Synergie (#68) : sans son
    fichier régional, il n'y a rien à afficher pour elle et le sélecteur ne doit pas
    proposer un périmètre qui produirait une page vide — comportement d'avant #95,
    conservé comme repli plutôt que remplacé par un message d'erreur."""
    import streamlit as st

    from utils import data_loader

    monkeypatch.setattr(data_loader, "DATA_2014_2020_NORMANDIE_PATH", FIXTURE / "chemin_absent.json")
    st.cache_data.clear()

    at = AppTest.from_file(str(PAGE_2014_2020), default_timeout=120).run()
    assert "Normandie" not in at.selectbox(key="perimetre_2014_2020").options


def test_pilotage_masque_sur_nouvelle_aquitaine_si_son_fichier_est_absent(donnees_fixture, monkeypatch):
    """Contrairement à Normandie, Nouvelle-Aquitaine reste sélectionnable même sans son
    fichier régional : elle figure, à la marge, dans les agrégats Synergie (#68). Sans le
    fichier, la page doit alors se rabattre sur le masquage plutôt que d'afficher un taux
    calculé sur cet engagé très partiel — exactement le piège que #95 corrige."""
    import streamlit as st

    from utils import data_loader

    monkeypatch.setattr(
        data_loader, "DATA_2014_2020_NOUVELLE_AQUITAINE_PATH", FIXTURE / "chemin_absent.json"
    )
    st.cache_data.clear()

    at = _rendre_perimetre_2014_2020("Nouvelle-Aquitaine")
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" in infos
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" not in textes


def test_pilotage_masque_sur_bretagne_si_son_fichier_est_absent(donnees_fixture, monkeypatch):
    """Même repli que Nouvelle-Aquitaine : sans le fichier officiel data.bretagne.bzh,
    Bretagne reste sélectionnable via ses 3 opérations marginales de Synergie (#68), mais
    la page se rabat sur le masquage plutôt que d'afficher un taux sur cet engagé très
    partiel (#95)."""
    import streamlit as st

    from utils import data_loader

    monkeypatch.setattr(data_loader, "DATA_2014_2020_BRETAGNE_PATH", FIXTURE / "chemin_absent.json")
    st.cache_data.clear()

    at = _rendre_perimetre_2014_2020("Bretagne")
    infos = " ".join(el.value for el in at.info)
    assert "Pas de taux de consommation sur ce périmètre" in infos
    textes = " ".join(el.value for el in at.markdown)
    assert "Programmé 2014-2020" not in textes
