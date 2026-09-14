"""Adaptation d'une source au dashboard (`dashboard/utils/periodes.py`, issues #83, #95).

Deux choses à protéger ici, et elles échouent toutes les deux en silence :

1. **la dérive avec le pipeline** — la table de renommage des colonnes duplique
   une information qui vit dans `data-pipeline/schema_source.py` (le dashboard
   n'importe pas le pipeline). Renommer une colonne d'un seul côté produirait une
   page vide, pas une erreur ;
2. **le taux de cofinancement, toujours recalculé** — montant / dépenses, sur
   les six sources 2014-2020 (2021-2027 fait exception, hors périmètre de #127 :
   seul le taux déclaré par son fichier existe). Un zéro à la place d'une valeur
   manquante se lirait comme une opération financée à 0 % par l'UE, ce qui est
   une information, alors qu'on n'en a aucune. Normandie, Nouvelle-Aquitaine et
   Bretagne portent aussi un taux déclaré dans leur fichier : conservé à part
   (`TAUX_COFINANCEMENT_DECLARE`) et signalé s'il diverge du recalculé de plus
   d'un point (`TAUX_COFINANCEMENT_DIVERGENT`) — jamais retenu comme le taux
   affiché, qui doit rester comparable entre les six sources (arbitrage Phase 4,
   #127 : les deux mesures ne concordaient pas systématiquement).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

pytest.importorskip("streamlit", reason="dépendances du dashboard non installées")

from schema_source import SCHEMAS  # noqa: E402

from utils.periodes import (  # noqa: E402
    CAPACITES,
    COLONNES_CANONIQUES,
    COLONNES_PAR_SOURCE,
    EXPLICATIONS_ABSENCES,
    PERIMETRE_FUSION,
    PERIODE_2014_2020,
    PERIODE_2021_2027,
    SEUIL_ECART_TAUX_DECLARE,
    SOURCE_2021_2027,
    SOURCE_BRETAGNE_2014_2020,
    SOURCE_NORMANDIE_2014_2020,
    SOURCE_NOUVELLE_AQUITAINE_2014_2020,
    SOURCE_PON_FSE_2014_2020,
    SOURCE_SYNERGIE_2014_2020,
    TAUX_COFINANCEMENT_DECLARE,
    TAUX_COFINANCEMENT_DIVERGENT,
    absences_expliquees,
    appliquer_libelles_programmes,
    capacites,
    capacites_source,
    enveloppes_ensemble_national_2014_2020,
    fusionner_ensemble_national_2014_2020,
    fusionner_enveloppes_sans_libelle,
    libelle_montant,
    normaliser_operations,
    pilotage_disponible,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dashboard"

FICHIER_PAR_SOURCE = {
    SOURCE_2021_2027: "data.json",
    SOURCE_SYNERGIE_2014_2020: "data_2014-2020.json",
    SOURCE_NORMANDIE_2014_2020: "data_2014-2020_normandie.json",
    SOURCE_NOUVELLE_AQUITAINE_2014_2020: "data_2014-2020_nouvelle_aquitaine.json",
    SOURCE_BRETAGNE_2014_2020: "data_2014-2020_bretagne_officiel.json",
    SOURCE_PON_FSE_2014_2020: "data_2014-2020_pon_fse.json",
}


def _libelles(source):
    return dict(SCHEMAS[source])


def _cles_fixture(nom):
    """Colonnes réellement présentes dans le fichier Parquet committé."""
    import pyarrow.parquet as pq

    parquet_nom = nom.replace(".json", ".parquet")
    return set(pq.read_schema(FIXTURE / parquet_nom).names)


@pytest.mark.parametrize("source", sorted(COLONNES_PAR_SOURCE))
def test_les_renommages_correspondent_au_schema_du_pipeline(source):
    """Le garde-fou contre la dérive : chaque libellé déclaré ici pour une source doit
    être celui que le pipeline lit réellement pour cette même source."""
    libelles_source = _libelles(source)
    for cle, libelle in COLONNES_PAR_SOURCE[source].items():
        assert libelles_source[cle] == libelle


def test_toute_colonne_aux_libelles_divergents_est_declaree():
    """L'oubli inverse, et le plus probable : une colonne commune à une source et au
    canonique 2021-2027 mais nommée différemment, qu'on aurait omis de déclarer. Elle
    resterait sous son libellé de source et le dashboard ne la trouverait pas.

    Comparé sur les **clés réelles des fixtures**, et non sur les libellés du schéma :
    deux transcriptions peuvent différer par une apostrophe ou une espace sans que les
    fichiers, eux, diffèrent (`build_cols` neutralise ces écarts — c'est le cas de
    `Département de l’opération`). Un test sur les libellés du schéma signalerait ces
    faux positifs et manquerait le vrai sujet, qui est la clé que le dashboard va
    effectivement chercher dans le JSON."""
    cols_2127 = _libelles(SOURCE_2021_2027)
    cles_2127 = _cles_fixture(FICHIER_PAR_SOURCE[SOURCE_2021_2027])

    for source in COLONNES_PAR_SOURCE:
        if source == SOURCE_2021_2027:
            continue
        cols_source = _libelles(source)
        cles_source = _cles_fixture(FICHIER_PAR_SOURCE[source])

        divergentes = {
            cle
            for cle in set(cols_2127) & set(cols_source)
            if cols_2127[cle] in cles_2127
            and cols_source[cle] in cles_source
            and cols_2127[cle] != cols_source[cle]
        }
        attendues = set(COLONNES_PAR_SOURCE[source])
        assert divergentes == attendues, (
            f"{source} : colonnes aux libellés divergents non déclarées : "
            f"{divergentes - attendues}"
        )


def test_colonnes_canoniques_couvrent_toutes_les_clefs_renommees():
    """Une clé renommée par une source mais absente de COLONNES_CANONIQUES lèverait un
    KeyError au chargement plutôt que de simplement échouer un test — ce garde-fou
    échoue au bon endroit, avec un message qui nomme la clé manquante."""
    for source, cols in COLONNES_PAR_SOURCE.items():
        for cle in cols:
            assert cle in COLONNES_CANONIQUES, f"{source} : clé {cle!r} sans libellé canonique"


def test_les_operations_2014_2020_prennent_les_libelles_canoniques():
    op = {
        "Montant UE programmé": 1000.0,
        "Total des dépenses éligibles programmées": 2000.0,
        "Libellé programme": "PO FEDER-FSE Bretagne 2014-2020",
        "Fonds": "FEDER",
    }
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2014_2020).iloc[0]

    assert normalisee["Montant UE"] == 1000.0
    assert normalisee["Total des dépenses éligibles"] == 2000.0
    assert normalisee["Libellé Programme"] == "PO FEDER-FSE Bretagne 2014-2020"
    assert normalisee["Fonds"] == "FEDER"
    # Les anciens libellés ne subsistent pas à côté des nouveaux : deux colonnes
    # portant le même montant fausseraient toute somme faite sur le DataFrame.
    assert "Montant UE programmé" not in normalisee
    assert "Total des dépenses éligibles programmées" not in normalisee


def test_le_taux_de_cofinancement_est_derive_des_deux_montants():
    op = {"Montant UE programmé": 850.0, "Total des dépenses éligibles programmées": 1000.0}
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2014_2020).iloc[0]
    assert normalisee["Taux de cofinancement"] == pytest.approx(0.85)


@pytest.mark.parametrize(
    "depenses",
    [0, None, float("nan")],
    ids=["depenses_nulles", "depenses_absentes", "depenses_nan"],
)
def test_le_taux_est_absent_plutot_que_nul_quand_il_est_indeterminable(depenses):
    """None, jamais 0 : un taux de 0 % se lit comme une opération sans financement
    UE, ce qui est un fait ; ici on n'a simplement pas de quoi le calculer."""
    op = {"Montant UE programmé": 850.0, "Total des dépenses éligibles programmées": depenses}
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2014_2020).iloc[0]
    assert pd.isna(normalisee["Taux de cofinancement"])


def test_le_taux_existant_de_2021_2027_n_est_pas_recalcule():
    """En 2021-2027 le taux est une colonne de la source. Le recalculer écraserait
    la valeur publiée par une valeur dérivée, silencieusement différente."""
    op = {"Montant UE": 500.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.42}
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2021_2027).iloc[0]
    assert normalisee["Taux de cofinancement"] == 0.42


@pytest.mark.parametrize(
    ("periode", "op"),
    [
        (PERIODE_2014_2020, {"Montant UE programmé": 10.0, "Total des dépenses éligibles programmées": 20.0}),
        # Le cas 2021-2027 n'est pas redondant : cette période ne renomme rien,
        # donc elle emprunte l'autre branche de la fonction — celle qui ne
        # recopie l'opération que pour ça. Testée sur la seule 2014-2020, la
        # recopie pouvait disparaître sans qu'aucun test ne rougisse (constaté
        # par mutation).
        (PERIODE_2021_2027, {"Montant UE": 10.0, "Total des dépenses éligibles": 20.0}),
    ],
    ids=["2014-2020", "2021-2027"],
)
def test_normaliser_ne_modifie_pas_les_operations_recues(periode, op):
    """Les opérations viennent d'un `st.cache_resource` partagé entre pages : les
    muter contaminerait le cache pour toute la session."""
    df = pd.DataFrame([op])
    avant = df.copy()
    result = normaliser_operations(df, periode)

    pd.testing.assert_frame_equal(df, avant)
    assert result.iloc[0]["Taux de cofinancement"] == pytest.approx(0.5)


def test_2021_2027_a_toutes_les_capacites():
    assert all(capacites(PERIODE_2021_2027).values())


def test_2014_2020_n_a_de_capacite_que_celles_qui_ont_ete_livrees():
    """Le détail compte plus que le total : une capacité passée à True sans que la
    donnée qui la porte existe viderait un bloc au lieu de le retirer. `plafonds_cofinancement`
    est vraie depuis #81 (catégories de la période transcrites), `montants_programmes` depuis
    #93 (dotations de l'Accord + maquettes REACT-EU transcrites) ; `dimension_thematique`
    reste fausse, la source ne la porte pas (#82) et aucune transcription n'y changera rien.

    Attention : `montants_programmes` vraie ne veut pas dire pilotage affiché partout —
    quatre périmètres en sont privés faute d'engagé comparable, voir
    `test_pilotage_masque_sur_les_perimetres_hors_synergie`."""
    assert capacites(PERIODE_2014_2020) == {
        "dimension_thematique": False,
        "montants_programmes": True,
        "plafonds_cofinancement": True,
        "perimetre_complet": False,
    }


def test_une_periode_inconnue_leve():
    """Plutôt qu'un dictionnaire vide, qui masquerait toute la page en silence."""
    with pytest.raises(KeyError):
        capacites("2028-2034")


def test_chaque_capacite_absente_est_expliquee_a_l_utilisateur():
    """Un bloc retiré sans explication se lit comme un oubli. Seul `perimetre_complet`
    échappe à la règle : ce n'est pas un bloc manquant mais une réserve sur les chiffres,
    portée par son propre avertissement.

    Exprimé sur les capacités **réellement absentes** d'au moins une période, et non sur
    l'ensemble des capacités déclarées : sans quoi livrer une capacité (ici
    `plafonds_cofinancement`, #81) obligerait à garder son explication, qui ne peut plus
    s'afficher et dont le texte contredit désormais l'écran."""
    absentes = {
        capacite
        for capacites_periode in CAPACITES.values()
        for capacite, presente in capacites_periode.items()
        if not presente
    } - {"perimetre_complet"}
    assert set(EXPLICATIONS_ABSENCES) == absentes
    assert len(absences_expliquees(PERIODE_2014_2020)) == len(absentes)
    assert absences_expliquees(PERIODE_2021_2027) == []


def test_le_libelle_du_montant_reste_celui_de_la_periode():
    """Normaliser la colonne ne rend pas les deux notions équivalentes : en
    2014-2020 le montant est programmé, en 2021-2027 conventionné."""
    assert libelle_montant(PERIODE_2014_2020) == "Montant UE programmé"
    assert libelle_montant(PERIODE_2021_2027) == "Montant UE"


# --- Enveloppes sans libellé de fonds correspondant (issue #93) ----------------


def test_enveloppe_react_eu_fondue_quand_aucune_operation_ne_la_porte():
    """Cas de la métropole : l'extraction Synergie n'y étiquette pas `FEDER REACT-EU`,
    ses opérations sont sous `FEDER`. Laisser les deux enveloppes séparées afficherait un
    REACT-EU à 0 % et un FEDER gonflé d'autant."""
    enveloppes, fusionnes = fusionner_enveloppes_sans_libelle(
        {"FEDER": 100, "FEDER REACT-EU": 30, "FSE": 50}, {"FEDER", "FSE"}
    )
    assert enveloppes == {"FEDER": 130, "FSE": 50}
    assert fusionnes == ["FEDER REACT-EU"]


def test_enveloppe_react_eu_conservee_quand_des_operations_la_portent():
    """Cas des DROM, seuls à porter le libellé : les deux enveloppes restent distinctes,
    sinon on perdrait un taux de consommation REACT-EU pourtant mesurable."""
    enveloppes, fusionnes = fusionner_enveloppes_sans_libelle(
        {"FEDER": 100, "FEDER REACT-EU": 30}, {"FEDER", "FEDER REACT-EU"}
    )
    assert enveloppes == {"FEDER": 100, "FEDER REACT-EU": 30}
    assert fusionnes == []


def test_pas_de_fusion_si_le_fonds_d_accueil_n_a_pas_d_enveloppe():
    """La maquette disparaîtrait dans un fonds sans dotation au lieu de rester visible."""
    enveloppes, fusionnes = fusionner_enveloppes_sans_libelle({"FEDER REACT-EU": 30}, {"FSE"})
    assert enveloppes == {"FEDER REACT-EU": 30}
    assert fusionnes == []


def test_fusionner_ne_modifie_pas_le_dictionnaire_recu():
    """Les enveloppes viennent d'un `st.cache_data` partagé entre sessions : les muter
    contaminerait les périmètres affichés ensuite (piège déjà vécu sur normaliser_operations)."""
    source = {"FEDER": 100, "FEDER REACT-EU": 30}
    fusionner_enveloppes_sans_libelle(source, {"FEDER"})
    assert source == {"FEDER": 100, "FEDER REACT-EU": 30}


def test_pilotage_disponible_sur_tous_les_perimetres():
    """Normandie, Nouvelle-Aquitaine et Bretagne ne dépendent plus d'une liste statique : leur
    pilotage dépend de la disponibilité de leur fichier régional sur le poste (#95), une
    décision prise par la page, pas par cette fonction — voir `test_dashboard_pages.py` pour
    le comportement écran, avec et sans fichier. Les deux périmètres agrégés (« Ensemble
    national », « Volet national ») ne sont plus exclus par construction depuis l'arbitrage
    Phase 4 (#121) : `fusionner_ensemble_national_2014_2020` leur donne à tous deux un engagé
    fusionné à opposer à une enveloppe."""
    assert pilotage_disponible("Ensemble national")
    assert pilotage_disponible("Volet national")
    assert pilotage_disponible("Normandie")
    assert pilotage_disponible("Nouvelle-Aquitaine")
    assert pilotage_disponible("Bretagne")
    assert pilotage_disponible("Corse")
    assert pilotage_disponible("Occitanie")


# --- Normalisation par source, hors Synergie (issue #95) -----------------------


def test_normandie_prend_les_libelles_canoniques():
    """Fichier bilingue franco-anglais : `Fond` (sans s) se renomme comme les autres.
    Le taux de cofinancement existe déjà en clair dans le fichier, mais c'est le taux
    RECALCULÉ (montant / dépenses) qui fait foi (arbitrage Phase 4, #127) — le déclaré
    est conservé à part, pour signal, pas pour remplacer le recalculé."""
    op = {
        "Fond": "FEDER",
        "Montant UE programmé": 170948.18,
        "Total des dépenses éligibles - Total eligible costs": 355154.47,
        "taux de cofinancement UE - EU co-financing rate": 0.48,
        "Nom du bénéficiaire - Beneficiary name": "COMUE Normandie Université",
        "Intitulé du projet - Operation name": "FED INV - Cloud souverain",
        "n° Dossier": "15E00020",
        "date début op. / start": "2015-01-01",
        "date fin d'op. / end": "2020-12-31",
        "CP / zip code": "14000",
        "Libellé programme": "Programme opérationnel Basse-Normandie 2014-2020",
    }
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_NORMANDIE_2014_2020).iloc[0]

    assert normalisee["Fonds"] == "FEDER"
    assert normalisee["Montant UE"] == 170948.18
    assert normalisee["Total des dépenses éligibles"] == 355154.47
    assert normalisee["Taux de cofinancement"] == pytest.approx(170948.18 / 355154.47)
    assert normalisee[TAUX_COFINANCEMENT_DECLARE] == pytest.approx(0.48)
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is False
    assert normalisee["Nom du bénéficiaire"] == "COMUE Normandie Université"
    assert normalisee["Numéro Opération"] == "15E00020"
    assert normalisee["Code postal du bénéficiaire"] == "14000"
    assert "Fond" not in normalisee
    assert "taux de cofinancement UE - EU co-financing rate" not in normalisee


def test_taux_declare_divergent_signale_sans_ecraser_le_recalcule():
    """Cas construit pour le seuil d'un point (#127) : taux déclaré 0,60, taux
    recalculé 0,50 (500/1000) — plus d'un point d'écart, donc signalé. Le taux
    affiché reste le recalculé, jamais le déclaré."""
    op = {
        "Fond": "FEDER",
        "Montant UE programmé": 500.0,
        "Total des dépenses éligibles - Total eligible costs": 1000.0,
        "taux de cofinancement UE - EU co-financing rate": 0.60,
        "n° Dossier": "TEST-001",
        "Libellé programme": "Programme test",
    }
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_NORMANDIE_2014_2020).iloc[0]

    assert normalisee["Taux de cofinancement"] == pytest.approx(0.5)
    assert normalisee[TAUX_COFINANCEMENT_DECLARE] == 0.60
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is True


def test_nouvelle_aquitaine_prend_les_libelles_canoniques():
    """Fichier tout en anglais : `Funds` (pas `Fond`, ni `Fonds`) se renomme aussi, et
    `libelle_prog` y reste un code CCI brut à ce stade — sa traduction en libellé humain
    est le rôle d'`appliquer_libelles_programmes`, pas de `normaliser_operations`."""
    op = {
        "Funds": "FEDER",
        "Amount co-financing European Union": 220000.0,
        "Total amount programmed": 550000.0,
        "Union co-financing rate (%)": 0.4,
        "Beneficiary name": "CIREF",
        "Operation name": "QualiCharlotte",
        "Operation number": 14310,
        "Colonne à masquer lors de la diffusion": "2014FR16M0OP001",
    }
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_NOUVELLE_AQUITAINE_2014_2020).iloc[0]

    assert normalisee["Fonds"] == "FEDER"
    assert normalisee["Montant UE"] == 220000.0
    assert normalisee["Total des dépenses éligibles"] == 550000.0
    assert normalisee["Taux de cofinancement"] == pytest.approx(0.4)  # recalculé, égal au déclaré ici
    assert normalisee[TAUX_COFINANCEMENT_DECLARE] == 0.4
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is False
    assert normalisee["Nom du bénéficiaire"] == "CIREF"
    assert normalisee["Libellé Programme"] == "2014FR16M0OP001"
    assert "Funds" not in normalisee


def test_appliquer_libelles_programmes_traduit_le_code_cci():
    """Nouvelle-Aquitaine ne nomme ses programmes que par ce code (issue #95, étape 1)."""
    df = pd.DataFrame([{"Libellé Programme": "2014FR16M0OP001"}, {"Libellé Programme": "2014FR16M0OP001"}])
    libelles = {"2014FR16M0OP001": "PO FEDER-FSE Nouvelle Aquitaine"}

    traduites = appliquer_libelles_programmes(df, libelles)

    assert (traduites["Libellé Programme"] == "PO FEDER-FSE Nouvelle Aquitaine").all()


def test_appliquer_libelles_programmes_garde_un_code_inconnu_tel_quel():
    """Un code absent de la table ne doit pas faire disparaître l'opération ni la
    rattacher à un mauvais programme — il reste visible tel quel, à corriger le jour où
    la table est complétée."""
    traduite = appliquer_libelles_programmes(pd.DataFrame([{"Libellé Programme": "CODE-INCONNU"}]), {}).iloc[0]
    assert traduite["Libellé Programme"] == "CODE-INCONNU"


def test_appliquer_libelles_programmes_ne_modifie_pas_les_operations_recues():
    df = pd.DataFrame([{"Libellé Programme": "2014FR16M0OP001"}])
    avant = df.copy()
    appliquer_libelles_programmes(df, {"2014FR16M0OP001": "PO Nouvelle-Aquitaine"})
    pd.testing.assert_frame_equal(df, avant)


def test_capacites_source_synergie_a_tout():
    capa = capacites_source(SOURCE_SYNERGIE_2014_2020)
    assert capa == {"trajectoire": True, "departement": True}


def test_capacites_source_normandie_sans_trajectoire():
    """Pas de `Date de programmation` dans ce fichier : la trajectoire disparaît, mais
    le rattachement départemental reste possible (le fichier porte un code postal)."""
    capa = capacites_source(SOURCE_NORMANDIE_2014_2020)
    assert capa == {"trajectoire": False, "departement": True}


def test_capacites_source_nouvelle_aquitaine_sans_trajectoire_ni_departement():
    """Ni date de programmation, ni code postal, ni département dans ce fichier."""
    capa = capacites_source(SOURCE_NOUVELLE_AQUITAINE_2014_2020)
    assert capa == {"trajectoire": False, "departement": False}


def test_capacites_source_bretagne_sans_trajectoire_mais_avec_departement():
    """Ni « Date de programmation » ni équivalent transposable dans ce fichier, mais un
    code postal d'opération qui rend le rattachement départemental possible — à la
    différence du premier fichier Bretagne (issue #95)."""
    capa = capacites_source(SOURCE_BRETAGNE_2014_2020)
    assert capa == {"trajectoire": False, "departement": True}


def test_capacites_source_par_defaut_permissive():
    """Une source non déclarée dans CAPACITES_SOURCE (2021-2027, qui n'en a pas besoin)
    n'a pas de restriction propre au-delà de CAPACITES — pas de faux négatif qui
    masquerait un bloc sans raison."""
    assert capacites_source(SOURCE_2021_2027) == {"trajectoire": True, "departement": True}


def test_taux_existant_invalide_devient_none():
    """Nouvelle-Aquitaine porte parfois `#DIV/0` en toutes lettres (formule Excel sur une
    dépense nulle) là où le taux déclaré devrait être un nombre. Laissé tel quel, il
    ferait basculer toute la colonne en dtype `object` au premier groupby en aval —
    constaté sur `compute_cofinancement_table`, qui plantait sur ce périmètre avant ce
    correctif. Le taux recalculé est de toute façon None ici (dépenses nulles) : les deux
    colonnes concordent sur l'absence de valeur, pas de divergence signalée."""
    op = {"Montant UE": 100.0, "Total des dépenses éligibles": 0.0, "Taux de cofinancement": "#DIV/0"}
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_NOUVELLE_AQUITAINE_2014_2020).iloc[0]
    assert pd.isna(normalisee["Taux de cofinancement"])
    assert pd.isna(normalisee[TAUX_COFINANCEMENT_DECLARE])
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is False


# --- Taux déclaré divergent (#127) : recalculer, comparer, signaler -----------


@pytest.mark.parametrize(
    "source",
    [SOURCE_NORMANDIE_2014_2020, SOURCE_NOUVELLE_AQUITAINE_2014_2020, SOURCE_BRETAGNE_2014_2020],
    ids=["normandie", "nouvelle-aquitaine", "bretagne"],
)
def test_source_regionale_recalcule_le_taux_au_lieu_de_garder_le_declare(source):
    """Pour les sources régionales 14-20, le taux affiché est toujours recalculé
    depuis les deux montants — pas celui du fichier. Les deux mesurent la même
    chose, mais ne concordent pas systématiquement (#127, 8 opérations, 23,8 M€).
    Le taux recalculé est homogène sur les six sources de la période."""
    op = {"Montant UE": 400.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.55}
    normalisee = normaliser_operations(pd.DataFrame([op]), source).iloc[0]
    assert normalisee["Taux de cofinancement"] == pytest.approx(0.4)


@pytest.mark.parametrize(
    "source",
    [SOURCE_NORMANDIE_2014_2020, SOURCE_NOUVELLE_AQUITAINE_2014_2020, SOURCE_BRETAGNE_2014_2020],
    ids=["normandie", "nouvelle-aquitaine", "bretagne"],
)
def test_source_regionale_conserve_le_taux_declare_a_part(source):
    """Le taux du fichier n'est pas perdu : il rejoint une colonne dédiée qui sert
    de signal de qualité de source, jamais de référence pour les plafonds."""
    op = {"Montant UE": 400.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.55}
    normalisee = normaliser_operations(pd.DataFrame([op]), source).iloc[0]
    assert normalisee[TAUX_COFINANCEMENT_DECLARE] == pytest.approx(0.55)


@pytest.mark.parametrize(
    "source",
    [SOURCE_NORMANDIE_2014_2020, SOURCE_NOUVELLE_AQUITAINE_2014_2020, SOURCE_BRETAGNE_2014_2020],
    ids=["normandie", "nouvelle-aquitaine", "bretagne"],
)
def test_taux_divergent_signale_quand_ecart_depasse_le_seuil(source):
    """Un écart > SEUIL_ECART_TAUX_DECLARE entre déclaré et recalculé vaut True."""
    ecart = SEUIL_ECART_TAUX_DECLARE + 0.001
    recalcule = 0.4
    declare = recalcule + ecart
    op = {"Montant UE": 400.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": declare}
    normalisee = normaliser_operations(pd.DataFrame([op]), source).iloc[0]
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is True


@pytest.mark.parametrize(
    "source",
    [SOURCE_NORMANDIE_2014_2020, SOURCE_NOUVELLE_AQUITAINE_2014_2020, SOURCE_BRETAGNE_2014_2020],
    ids=["normandie", "nouvelle-aquitaine", "bretagne"],
)
def test_taux_non_divergent_quand_ecart_sous_le_seuil(source):
    """Un écart <= SEUIL_ECART_TAUX_DECLARE vaut False : les deux mesures concordent."""
    ecart = SEUIL_ECART_TAUX_DECLARE * 0.5
    recalcule = 0.4
    declare = recalcule + ecart
    op = {"Montant UE": 400.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": declare}
    normalisee = normaliser_operations(pd.DataFrame([op]), source).iloc[0]
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is False


def test_taux_divergent_false_quand_declare_invalide():
    """Nouvelle-Aquitaine avec `#DIV/0` : le déclaré est NaN, pas de comparaison possible,
    divergent est False — pas un signal d'écart, juste une absence."""
    op = {"Montant UE": 100.0, "Total des dépenses éligibles": 0.0, "Taux de cofinancement": "#DIV/0"}
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_NOUVELLE_AQUITAINE_2014_2020).iloc[0]
    assert bool(normalisee[TAUX_COFINANCEMENT_DIVERGENT]) is False
    assert pd.isna(normalisee[TAUX_COFINANCEMENT_DECLARE])


def test_synergie_n_a_pas_de_taux_declare_ni_divergent():
    """Synergie ne porte pas de taux dans le fichier : rien à comparer, ces colonnes
    n'existent pas — les ajouter à vide polluerait les groupby en aval."""
    op = {"Montant UE programmé": 850.0, "Total des dépenses éligibles programmées": 1000.0}
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2014_2020).iloc[0]
    assert TAUX_COFINANCEMENT_DECLARE not in normalisee.index
    assert TAUX_COFINANCEMENT_DIVERGENT not in normalisee.index


def test_2021_2027_n_a_pas_de_taux_declare_ni_divergent():
    """Hors périmètre de #127 : le taux du fichier est la seule mesure disponible."""
    op = {"Montant UE": 500.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.42}
    normalisee = normaliser_operations(pd.DataFrame([op]), PERIODE_2021_2027).iloc[0]
    assert TAUX_COFINANCEMENT_DECLARE not in normalisee.index
    assert TAUX_COFINANCEMENT_DIVERGENT not in normalisee.index


def test_normaliser_source_regionale_ne_modifie_pas_le_dataframe_recu():
    """Même invariant que test_normaliser_ne_modifie_pas_les_operations_recues,
    étendu au chemin #127 qui ajoute des colonnes."""
    op = {"Montant UE": 400.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.55}
    df = pd.DataFrame([op])
    avant = df.copy()
    normaliser_operations(df, SOURCE_NORMANDIE_2014_2020)
    pd.testing.assert_frame_equal(df, avant)


def test_capacites_source_periode_synergie_equivaut_a_sa_source():
    """`PERIODE_2014_2020` et `SOURCE_SYNERGIE_2014_2020` sont la même chaîne : la
    fonction ne doit pas les traiter différemment selon l'import utilisé pour l'appeler."""
    assert capacites_source(PERIODE_2014_2020) == capacites_source(SOURCE_SYNERGIE_2014_2020)


# --- PON FSE : sept programmes à router, pas un périmètre régional (issue #95, point 3) --


def test_pon_fse_prend_les_libelles_canoniques():
    """Ni code postal ni NUMCCI dans ce fichier (voir COLONNES_PON_FSE_2014_2020) : seules
    les clés effectivement présentes sont vérifiées ici."""
    op = {
        "num_dossier": "201603870",
        "Libellé_po": "Programme Opérationnel National FSE",
        "Region_adm": "Alsace",
        "Lib_org": "Collectivité européenne d'Alsace",
        "Lib_opé": "ASSISTANCE TECHNIQUE 2015-2016",
        "Dépenses totales": 76800.03,
        "Mont_UE": 38400.0,
        "Date début réalisation": "2015-10-01",
        "Date fin réalisation": "2016-12-31",
        "Fonds": "FSE",
    }
    normalisee = normaliser_operations(pd.DataFrame([op]), SOURCE_PON_FSE_2014_2020).iloc[0]

    assert normalisee["Numéro Opération"] == "201603870"
    assert normalisee["Libellé Programme"] == "Programme Opérationnel National FSE"
    assert normalisee["Nom du bénéficiaire"] == "Collectivité européenne d'Alsace"
    assert normalisee["Intitulé du projet"] == "ASSISTANCE TECHNIQUE 2015-2016"
    assert normalisee["Total des dépenses éligibles"] == 76800.03
    assert normalisee["Montant UE"] == 38400.0
    assert normalisee["Fonds"] == "FSE"
    # `Fonds` ne se renomme pas (déjà canonique, comme pour Synergie) : présent une
    # seule fois, jamais dupliqué sous une clé source qui n'existe pas.
    assert "Mont_UE" not in normalisee


def test_capacites_source_pon_fse_sans_trajectoire_ni_departement():
    """Ni code postal ni NUMCCI dans ce fichier : aucun rattachement départemental. `Date
    début/fin réalisation` existe mais date l'exécution, pas la programmation."""
    assert capacites_source(SOURCE_PON_FSE_2014_2020) == {"trajectoire": False, "departement": False}


# Relevé indépendant des sept valeurs de `Libellé_po` et de leur région, depuis le
# commentaire de l'issue #95 (point 3) et l'Accord de partenariat p.171 (Mayotte) — pas
# depuis `REGIONS_PON_FSE_2014_2020` lui-même, qui ne pourrait pas se tromper à ses
# propres yeux (mutation).
REGIONS_ATTENDUES_PON_FSE = {
    "Programme Opérationnel National FSE": None,
    "Programme Opérationnel IEJ": None,
    "PO réunion": "La Réunion",
    "PO Guadeloupe": "Guadeloupe",
    "PO Martinique": "Martinique",
    "PO Guyane": "Guyane",
    "PO Mayotte": "Mayotte",
}


def test_regions_pon_fse_route_les_sept_programmes():
    from utils.periodes import REGIONS_PON_FSE_2014_2020

    assert REGIONS_PON_FSE_2014_2020 == REGIONS_ATTENDUES_PON_FSE


# --- Fusion « Ensemble national » 2014-2020 (arbitrage Phase 4, issue #121) -----


def test_fusion_ensemble_national_substitue_et_additionne():
    """Cas construit couvrant les deux règles à la fois, sur un jeu minimal :
    - Bretagne a son fichier propre (`ops_hors_synergie_par_region`) : sa ligne Synergie
      marginale (BZH001) est ignorée, seule celle du fichier régional (BZH-OFF-1) compte ;
    - Nouvelle-Aquitaine N'A PAS de fichier chargé ici (absente du dict) : sa ligne Synergie
      (NAQ001) reste incluse, en repli — pas silencieusement perdue ;
    - le national et l'interrégional Synergie sont traités différemment : le national est
      gardé (`national`), l'interrégional est écarté (aucune vue n'a de case pour lui) ;
    - le PON FSE s'ajoute, routé par programme et non par la région portée par la ligne
      (PON001, région Guadeloupe portée par la ligne mais programme national → 'national')."""
    ops_synergie = pd.DataFrame([
        {"Fonds": "FEDER", "Montant UE": 100.0, "regions_modernes": ["Bretagne"], "is_national": False, "is_interregional": False},
        {"Fonds": "FEDER", "Montant UE": 200.0, "regions_modernes": ["Nouvelle-Aquitaine"], "is_national": False, "is_interregional": False},
        {"Fonds": "FEDER", "Montant UE": 300.0, "regions_modernes": ["Occitanie"], "is_national": False, "is_interregional": False},
        {"Fonds": "FSE", "Montant UE": 50.0, "regions_modernes": [], "is_national": True, "is_interregional": False},
        {"Fonds": "FSE", "Montant UE": 999.0, "regions_modernes": ["Bretagne", "Occitanie"], "is_national": False, "is_interregional": True},
    ])
    ops_hors_synergie_par_region = {
        "Bretagne": pd.DataFrame([{"Fonds": "FEDER", "Montant UE": 150.0}]),
    }
    ops_pon_fse = pd.DataFrame([
        {"Fonds": "FSE", "Montant UE": 10.0, "Libellé Programme": "PO Guadeloupe", "regions_modernes": ["Guadeloupe"]},
        {"Fonds": "FSE", "Montant UE": 20.0, "Libellé Programme": "Programme Opérationnel National FSE"},
    ])

    fusion = fusionner_ensemble_national_2014_2020(ops_synergie, ops_hors_synergie_par_region, ops_pon_fse)
    montants_par_perimetre = fusion.groupby(PERIMETRE_FUSION)["Montant UE"].apply(sorted).to_dict()

    assert montants_par_perimetre["Bretagne"] == [150.0]
    assert montants_par_perimetre["Nouvelle-Aquitaine"] == [200.0]
    assert montants_par_perimetre["Occitanie"] == [300.0]
    assert montants_par_perimetre["national"] == [20.0, 50.0]
    assert montants_par_perimetre["Guadeloupe"] == [10.0]
    assert len(fusion) == 6


def test_enveloppes_ensemble_national_fusionne_par_perimetre_avant_de_sommer():
    """Cas construit sur le mécanisme du #96 : un DROM garde ses deux lignes FEDER/FEDER
    REACT-EU (il porte des opérations sous ce libellé), une région métropolitaine les
    fusionne (elle n'en porte aucune) — la décision se prend AVANT la somme nationale, pas
    après, sinon la présence d'opérations REACT-EU quelque part en France fusionnerait à
    tort l'enveloppe d'une région qui n'en a pas."""
    totaux = {
        "La Réunion": {"FEDER": 100.0, "FEDER REACT-EU": 20.0},
        "Occitanie": {"FEDER": 200.0, "FEDER REACT-EU": 30.0},
        "national": {"FSE": 50.0},
    }
    fonds_engages = {
        "La Réunion": {"FEDER", "FEDER REACT-EU"},
        "Occitanie": {"FEDER"},
        "national": {"FSE"},
    }
    enveloppes, fonds_fusionnes = enveloppes_ensemble_national_2014_2020(fonds_engages, totaux)

    assert enveloppes["FEDER REACT-EU"] == 20.0
    assert enveloppes["FEDER"] == pytest.approx(100.0 + 200.0 + 30.0)
    assert enveloppes["FSE"] == 50.0
    assert fonds_fusionnes == ["FEDER REACT-EU"]


# Les trois régions qui se substituent à Synergie (issue #95). Épinglées ici parce
# que la table a désormais **plusieurs consommateurs hors du dashboard** : les vues
# SQL de `metabase/init/` la réécrivent (issue #125) et le codegen dbt l'importe
# (issue #135). Une quatrième région qui publierait son fichier doit être ajoutée
# partout ; ce test fait échouer la suite si on ne l'ajoute qu'ici, et sert de
# rappel de la liste des endroits à mettre à jour.
REGIONS_SUBSTITUEES_ATTENDUES = {
    "Normandie": "2014-2020-normandie",
    "Nouvelle-Aquitaine": "2014-2020-nouvelle-aquitaine",
    "Bretagne": "2014-2020-bretagne-officiel",
}


def test_regions_substituees_pointent_sur_leur_source():
    from utils.periodes import REGIONS_SUBSTITUEES_2014_2020

    assert REGIONS_SUBSTITUEES_2014_2020 == REGIONS_SUBSTITUEES_ATTENDUES


def test_regions_substituees_sont_des_cles_de_sources_connues():
    """Chaque valeur doit être une clé réelle de `sources.SOURCES`.

    Sinon la page charge un fichier qui n'existe pas et se rabat silencieusement
    sur le sous-comptage Synergie — exactement le défaut que #95 a corrigé.
    """
    sys.path.insert(0, str(RACINE / "data-pipeline"))
    from sources import SOURCES

    from utils.periodes import REGIONS_SUBSTITUEES_2014_2020

    for region, source_id in REGIONS_SUBSTITUEES_2014_2020.items():
        assert source_id in SOURCES, f"{region} pointe sur une source inconnue : {source_id}"


def test_la_page_2014_2020_ne_redefinit_pas_la_table():
    """La page doit IMPORTER la règle, pas en garder une copie.

    Elle l'a longtemps définie en propre (`SOURCE_HORS_SYNERGIE`), ce qui la
    rendait inaccessible à tout script — un module Streamlit ne s'importe pas.
    Ce test empêche le retour en arrière.
    """
    page = (RACINE / "dashboard" / "pages" / "5_Période_2014-2020.py").read_text(
        encoding="utf-8"
    )
    assert "REGIONS_SUBSTITUEES_2014_2020" in page
    assert '"Normandie": SOURCE_NORMANDIE_2014_2020' not in page
