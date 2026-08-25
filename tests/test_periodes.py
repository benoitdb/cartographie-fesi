"""Adaptation d'une période au dashboard (`dashboard/utils/periodes.py`, issue #83).

Deux choses à protéger ici, et elles échouent toutes les deux en silence :

1. **la dérive avec le pipeline** — la table d'équivalence des colonnes duplique
   une information qui vit dans `data-pipeline/schema_source.py` (le dashboard
   n'importe pas le pipeline). Renommer une colonne d'un seul côté produirait une
   page vide, pas une erreur ;
2. **le taux de cofinancement dérivé** — il n'existe pas dans le fichier
   2014-2020 et se calcule. Un zéro à la place d'une valeur manquante se lirait
   comme une opération financée à 0 % par l'UE, ce qui est une information, alors
   qu'on n'en a aucune.
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
    COLONNES_EQUIVALENTES,
    EXPLICATIONS_ABSENCES,
    PERIODE_2014_2020,
    PERIODE_2021_2027,
    absences_expliquees,
    capacites,
    fusionner_enveloppes_sans_libelle,
    libelle_montant,
    normaliser_operations,
    pilotage_disponible,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dashboard"


def _libelles(periode):
    return dict(SCHEMAS[periode])


def _cles_fixture(nom):
    """Clés réellement présentes sur une opération du fichier committé."""
    operations = json.loads((FIXTURE / nom).read_text(encoding="utf-8"))["operations"]
    return set(operations[0])


def test_les_equivalences_correspondent_aux_schemas_du_pipeline():
    """Le garde-fou contre la dérive : chaque paire de libellés déclarée ici doit
    être celle que le pipeline lit réellement, des deux côtés."""
    for cle, (libelle_2127, libelle_1420) in COLONNES_EQUIVALENTES.items():
        assert _libelles(PERIODE_2021_2027)[cle] == libelle_2127
        assert _libelles(PERIODE_2014_2020)[cle] == libelle_1420


def test_toute_colonne_aux_libelles_divergents_est_declaree():
    """L'oubli inverse, et le plus probable : une colonne commune aux deux
    périodes mais nommée différemment, qu'on aurait omis de déclarer. Elle
    resterait sous son libellé 2014-2020 et le dashboard ne la trouverait pas.

    Comparé sur les **clés réelles des fixtures**, et non sur les libellés du
    schéma : deux transcriptions peuvent différer par une apostrophe ou une
    espace sans que les fichiers, eux, diffèrent (`build_cols` neutralise ces
    écarts — c'est le cas de `Département de l’opération`). Un test sur les
    libellés du schéma signalerait ces faux positifs et manquerait le vrai sujet,
    qui est la clé que le dashboard va effectivement chercher dans le JSON."""
    cols_2127, cols_1420 = _libelles(PERIODE_2021_2027), _libelles(PERIODE_2014_2020)
    cles_2127, cles_1420 = _cles_fixture("data.json"), _cles_fixture("data_2014-2020.json")

    divergentes = {
        cle
        for cle in set(cols_2127) & set(cols_1420)
        if cols_2127[cle] in cles_2127
        and cols_1420[cle] in cles_1420
        and cols_2127[cle] != cols_1420[cle]
    }
    assert divergentes == set(COLONNES_EQUIVALENTES), (
        f"colonnes aux libellés divergents non déclarées : {divergentes - set(COLONNES_EQUIVALENTES)}"
    )


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


def test_pilotage_masque_sur_les_quatre_perimetres_hors_synergie():
    assert not pilotage_disponible("Bretagne")
    assert not pilotage_disponible("Normandie")
    assert not pilotage_disponible("Nouvelle-Aquitaine")
    assert not pilotage_disponible("Ensemble national", est_national=True)
    assert pilotage_disponible("Corse")
    assert pilotage_disponible("Occitanie")
