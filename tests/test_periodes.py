"""Adaptation d'une source au dashboard (`dashboard/utils/periodes.py`, issues #83, #95).

Deux choses à protéger ici, et elles échouent toutes les deux en silence :

1. **la dérive avec le pipeline** — la table de renommage des colonnes duplique
   une information qui vit dans `data-pipeline/schema_source.py` (le dashboard
   n'importe pas le pipeline). Renommer une colonne d'un seul côté produirait une
   page vide, pas une erreur ;
2. **le taux de cofinancement dérivé** — il n'existe pas dans le fichier
   Synergie et se calcule. Un zéro à la place d'une valeur manquante se lirait
   comme une opération financée à 0 % par l'UE, ce qui est une information, alors
   qu'on n'en a aucune. Normandie et Nouvelle-Aquitaine, elles, portent déjà ce
   taux en clair : rien à dériver, `normaliser_operations` ne doit pas l'écraser.
"""

import json
import sys
from pathlib import Path

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
    PERIODE_2014_2020,
    PERIODE_2021_2027,
    SOURCE_2021_2027,
    SOURCE_BRETAGNE_2014_2020,
    SOURCE_NORMANDIE_2014_2020,
    SOURCE_NOUVELLE_AQUITAINE_2014_2020,
    SOURCE_PON_FSE_2014_2020,
    SOURCE_SYNERGIE_2014_2020,
    absences_expliquees,
    appliquer_libelles_programmes,
    capacites,
    capacites_source,
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
    """Clés réellement présentes sur une opération du fichier committé."""
    operations = json.loads((FIXTURE / nom).read_text(encoding="utf-8"))["operations"]
    return set(operations[0])


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
    (normalisee,) = normaliser_operations([op], PERIODE_2014_2020)

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
    (normalisee,) = normaliser_operations([op], PERIODE_2014_2020)
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
    (normalisee,) = normaliser_operations([op], PERIODE_2014_2020)
    assert normalisee["Taux de cofinancement"] is None


def test_le_taux_existant_de_2021_2027_n_est_pas_recalcule():
    """En 2021-2027 le taux est une colonne de la source. Le recalculer écraserait
    la valeur publiée par une valeur dérivée, silencieusement différente."""
    op = {"Montant UE": 500.0, "Total des dépenses éligibles": 1000.0, "Taux de cofinancement": 0.42}
    (normalisee,) = normaliser_operations([op], PERIODE_2021_2027)
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
    """Les opérations viennent d'un `st.cache_data` partagé entre pages : les
    muter contaminerait le cache pour toute la session."""
    avant = dict(op)
    normalisees = normaliser_operations([op], periode)

    assert op == avant
    # Et la copie, elle, porte bien le taux dérivé : sans quoi le test passerait
    # aussi sur une fonction qui ne fait plus rien.
    assert normalisees[0]["Taux de cofinancement"] == pytest.approx(0.5)


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


def test_pilotage_masque_plus_que_sur_les_perimetres_agreges():
    """Normandie, Nouvelle-Aquitaine et Bretagne sont sorties de la liste statique : leur
    pilotage ne dépend plus de la période mais de la disponibilité de leur fichier régional
    sur le poste (#95), une décision prise par la page, pas par cette fonction — voir
    `test_dashboard_pages.py` pour le comportement écran, avec et sans fichier."""
    assert not pilotage_disponible("Ensemble national", est_national=True)
    assert not pilotage_disponible("Volet national", est_national=True)
    assert pilotage_disponible("Normandie")
    assert pilotage_disponible("Nouvelle-Aquitaine")
    assert pilotage_disponible("Bretagne")
    assert pilotage_disponible("Corse")
    assert pilotage_disponible("Occitanie")


# --- Normalisation par source, hors Synergie (issue #95) -----------------------


def test_normandie_prend_les_libelles_canoniques():
    """Fichier bilingue franco-anglais : `Fond` (sans s) se renomme comme les autres,
    et le taux de cofinancement existe déjà en clair — il ne doit pas être recalculé
    (contrairement à Synergie, qui ne le porte pas)."""
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
    (normalisee,) = normaliser_operations([op], SOURCE_NORMANDIE_2014_2020)

    assert normalisee["Fonds"] == "FEDER"
    assert normalisee["Montant UE"] == 170948.18
    assert normalisee["Total des dépenses éligibles"] == 355154.47
    assert normalisee["Taux de cofinancement"] == 0.48
    assert normalisee["Nom du bénéficiaire"] == "COMUE Normandie Université"
    assert normalisee["Numéro Opération"] == "15E00020"
    assert normalisee["Code postal du bénéficiaire"] == "14000"
    assert "Fond" not in normalisee
    assert "taux de cofinancement UE - EU co-financing rate" not in normalisee


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
    (normalisee,) = normaliser_operations([op], SOURCE_NOUVELLE_AQUITAINE_2014_2020)

    assert normalisee["Fonds"] == "FEDER"
    assert normalisee["Montant UE"] == 220000.0
    assert normalisee["Total des dépenses éligibles"] == 550000.0
    assert normalisee["Taux de cofinancement"] == 0.4
    assert normalisee["Nom du bénéficiaire"] == "CIREF"
    assert normalisee["Libellé Programme"] == "2014FR16M0OP001"
    assert "Funds" not in normalisee


def test_appliquer_libelles_programmes_traduit_le_code_cci():
    """Nouvelle-Aquitaine ne nomme ses programmes que par ce code (issue #95, étape 1)."""
    operations = [{"Libellé Programme": "2014FR16M0OP001"}, {"Libellé Programme": "2014FR16M0OP001"}]
    libelles = {"2014FR16M0OP001": "PO FEDER-FSE Nouvelle Aquitaine"}

    traduites = appliquer_libelles_programmes(operations, libelles)

    assert all(op["Libellé Programme"] == "PO FEDER-FSE Nouvelle Aquitaine" for op in traduites)


def test_appliquer_libelles_programmes_garde_un_code_inconnu_tel_quel():
    """Un code absent de la table ne doit pas faire disparaître l'opération ni la
    rattacher à un mauvais programme — il reste visible tel quel, à corriger le jour où
    la table est complétée."""
    (traduite,) = appliquer_libelles_programmes([{"Libellé Programme": "CODE-INCONNU"}], {})
    assert traduite["Libellé Programme"] == "CODE-INCONNU"


def test_appliquer_libelles_programmes_ne_modifie_pas_les_operations_recues():
    op = {"Libellé Programme": "2014FR16M0OP001"}
    avant = dict(op)
    appliquer_libelles_programmes([op], {"2014FR16M0OP001": "PO Nouvelle-Aquitaine"})
    assert op == avant


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
    dépense nulle) là où le taux devrait être un nombre. Laissé tel quel, il ferait
    basculer toute la colonne en dtype `object` au premier groupby en aval — constaté sur
    `compute_cofinancement_table`, qui plantait sur ce périmètre avant ce correctif."""
    op = {"Montant UE": 100.0, "Total des dépenses éligibles": 0.0, "Taux de cofinancement": "#DIV/0"}
    (normalisee,) = normaliser_operations([op], SOURCE_NOUVELLE_AQUITAINE_2014_2020)
    assert normalisee["Taux de cofinancement"] is None


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
    (normalisee,) = normaliser_operations([op], SOURCE_PON_FSE_2014_2020)

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
