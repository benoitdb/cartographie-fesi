"""Plafonds de cofinancement UE et regroupement en catégories affichables.

`utils/cofinancement.py` traduit une règle de droit (règlement (UE) 2021/1060,
art. 112 : 85% / 60% / 50% selon la catégorie de région, 85% pour les RUP) en
taux utilisés ensuite comme repère de contrôle dans le dashboard. Une erreur
ici ne casse rien visiblement : elle déplace le losange « plafond
réglementaire » et fait passer des opérations pour conformes, ou l'inverse.

Les cas couverts sont ceux que la donnée réelle contient effectivement :
libellés des trois catégories, catégorie mixte pondérée telle que transcrite
dans `region_metadata.json`, et régions ultrapériphériques.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.cofinancement import (  # noqa: E402
    bucket_categorie,
    est_hors_plafond,
    filtrer_fonds_plafonnes,
    libelle_categorie_2014_2020,
    plafond_categorie,
    plafond_intervalle_2014_2020,
)

# Libellé mixte tel qu'il apparaît réellement dans region_metadata.json
# (Auvergne-Rhône-Alpes) : c'est ce format-là que la regex doit savoir lire.
MIXTE_ARA = "Mixte : 57% Plus développée / 43% En transition (FEDER)"


def test_les_trois_categories_ont_leur_plafond_reglementaire():
    assert plafond_categorie("plus développée") == 0.50
    assert plafond_categorie("en transition") == 0.60
    assert plafond_categorie("moins développée") == 0.85


def test_le_libelle_est_reconnu_quelle_que_soit_la_casse_et_les_espaces():
    """Les libellés viennent de `region_metadata.json`, saisi à la main : une
    majuscule ou une espace de plus ne doit pas faire tomber le plafond à None,
    ce qui masquerait silencieusement le repère réglementaire."""
    assert plafond_categorie("  Moins Développée ") == 0.85


def test_une_categorie_mixte_donne_la_moyenne_ponderee_des_plafonds():
    # 57% × 0,50 + 43% × 0,60 = 0,543
    assert plafond_categorie(MIXTE_ARA) == pytest.approx(0.543)


def test_une_region_ultraperipherique_a_toujours_le_plafond_le_plus_eleve():
    """85% quelle que soit la catégorie de base (art. 349 TFUE) — y compris
    quand la catégorie est absente, cas des territoires mal renseignés."""
    assert plafond_categorie("plus développée", ultraperipherique=True) == 0.85
    assert plafond_categorie(None, ultraperipherique=True) == 0.85


def test_une_categorie_absente_ou_non_reconnue_ne_produit_pas_de_plafond():
    """None, et non une valeur par défaut : un plafond inventé serait affiché
    comme un repère réglementaire alors qu'il ne repose sur rien."""
    assert plafond_categorie(None) is None
    assert plafond_categorie("") is None
    assert plafond_categorie("Catégorie inconnue") is None
    assert plafond_categorie("Mixte : 100% Catégorie inconnue") is None


def test_le_bucket_affiche_la_categorie_avec_une_majuscule():
    assert bucket_categorie("moins développée") == "Moins développée"


def test_le_bucket_signale_les_regions_ultraperipheriques_a_part():
    """Une RUP ne doit pas être agrégée avec les régions de sa catégorie de
    base : son plafond est différent, la comparer aux autres induirait en
    erreur."""
    assert bucket_categorie("moins développée", ultraperipherique=True) == "Moins développée + RUP"


def test_le_bucket_replie_toutes_les_categories_mixtes_sur_un_seul_libelle():
    """Sans ça, chaque région mixte formerait sa propre catégorie d'affichage
    (les pondérations diffèrent), et le graphe national par catégorie
    compterait autant de barres que de régions."""
    assert bucket_categorie(MIXTE_ARA) == "Mixte"


def test_le_bucket_nomme_explicitement_l_absence_de_categorie():
    assert bucket_categorie(None) == "Non classifiée"
    assert bucket_categorie("") == "Non classifiée"


# ---------------------------------------------------------------- 2014-2020 (issue #81)
#
# La période a deux particularités qu'aucun test 2021-2027 ne peut attraper : six régions
# modernes sur treize réunissent des anciennes régions de catégories différentes, et le
# fonds REACT-EU déroge aux plafonds. Une erreur sur l'une ou l'autre est invisible à
# l'écran — un plafond faux reste un plafond d'allure plausible.

# Forme réelle de data/processed/categories_ue_2014_2020.json, produite par
# data-pipeline/categories_ue_2014_2020.py.
NORMANDIE_MIXTE = {
    "categorie_ue": None,
    "composantes": [["Basse-Normandie", "en transition"], ["Haute-Normandie", "plus développée"]],
}
BRETAGNE_HOMOGENE = {
    "categorie_ue": "plus développée",
    "composantes": [["Bretagne", "plus développée"]],
}


def test_une_region_homogene_a_un_plafond_unique():
    """Intervalle dégénéré (min == max) et non un scalaire : l'appelant traite les deux cas
    par le même chemin, et une région homogène ne doit pas emprunter une branche à part."""
    assert plafond_intervalle_2014_2020(BRETAGNE_HOMOGENE) == (0.50, 0.50)


def test_une_region_mixte_donne_la_fourchette_de_ses_anciennes_regions():
    """Et non une moyenne : les programmes 2014-2020 sont bâtis par ancienne région, chacun
    mono-catégorie, donc le plafond réel dépend de l'ancienne région dont relève l'opération.
    Moyenner produirait un nombre qu'aucune opération ne peut dépasser légitimement."""
    assert plafond_intervalle_2014_2020(NORMANDIE_MIXTE) == (0.50, 0.60)


def test_une_region_absente_du_referentiel_n_a_pas_de_plafond():
    """None plutôt qu'un plafond par défaut : Saint-Martin n'a pas de code NUTS2010 propre
    et n'est pas dans le fichier. Un repli sur 85 % rendrait toute opération conforme."""
    assert plafond_intervalle_2014_2020(None) is None
    assert plafond_intervalle_2014_2020({"categorie_ue": None, "composantes": []}) is None


def test_une_categorie_2014_2020_inconnue_ne_produit_pas_de_plafond():
    """Le repli silencieux qu'il ne faut pas : un libellé mal transcrit doit faire
    disparaître le plafond, pas en inventer un."""
    assert plafond_intervalle_2014_2020({"categorie_ue": "ultrapériphérique", "composantes": []}) is None


def test_le_libelle_d_une_region_mixte_nomme_les_anciennes_regions():
    """« Mixte » seul se lirait comme une donnée manquante plutôt que comme un découpage
    disparu — c'est justement ce que l'utilisateur doit pouvoir comprendre."""
    libelle = libelle_categorie_2014_2020(NORMANDIE_MIXTE)
    assert "Basse-Normandie : en transition" in libelle
    assert "Haute-Normandie : plus développée" in libelle
    assert libelle_categorie_2014_2020(BRETAGNE_HOMOGENE) == "Plus développée"
    assert libelle_categorie_2014_2020(None) == "Non classifiée"


def test_les_trois_fonds_hors_article_120_sont_exclus_des_plafonds():
    """Chacun pour une raison distincte, toutes trois écrites dans un texte : REACT-EU déroge
    (2020/2221 art. 92 ter §12), l'IEJ voit son plafond relevé par l'art. 120 §3 lui-même, et
    le FEAD n'est pas un Fonds ESI (transfert hors enveloppe, art. 94 ; règlement 223/2014)."""
    for fonds in ("FEDER REACT-EU", "IEJ", "FEAD"):
        assert est_hors_plafond(fonds)


def test_les_fonds_relevant_de_l_article_120_restent_plafonnes():
    """L'exclusion doit rester étroite : élargie au FEDER ou au FSE, elle viderait le contrôle
    de son objet sans rien afficher de différent."""
    for fonds in ("FEDER", "FSE", "FEDER-FSE"):
        assert not est_hors_plafond(fonds)


def test_un_fonds_n_est_pas_exclu_par_sous_chaine():
    """Le libellé exact, pas un `in` : un futur fonds mentionnant REACT-EU sans relever de la
    dérogation de l'art. 92 ter §12 échapperait autrement à tout plafond."""
    assert not est_hors_plafond("FSE REACT-EU")


def test_les_operations_react_eu_sortent_du_decompte_des_depassements():
    """Leur médiane est à 100 % par construction : les comparer aux plafonds de droit commun
    produirait un faux positif garanti, sur 593 opérations dans le fichier réel."""
    df = pd.DataFrame(
        {
            "Fonds": ["FEDER", "FEDER REACT-EU", "FSE", "IEJ", "FEAD"],
            "Taux de cofinancement": [0.55, 1.0, 0.45, 0.75, 0.85],
        }
    )
    plafonnees, ecartees = filtrer_fonds_plafonnes(df)

    assert ecartees == 3
    assert list(plafonnees["Fonds"]) == ["FEDER", "FSE"]


def test_le_nombre_d_operations_ecartees_est_rendu_a_l_appelant():
    """La page doit pouvoir dire combien d'opérations sortent du décompte : sans ce nombre,
    l'écart entre le tableau descriptif et le décompte des dépassements se lit comme une perte."""
    df = pd.DataFrame({"Fonds": ["FEDER", "FSE"], "Taux de cofinancement": [0.55, 0.45]})
    plafonnees, ecartees = filtrer_fonds_plafonnes(df)

    assert ecartees == 0
    assert len(plafonnees) == 2


def test_l_absence_de_colonne_fonds_ne_fait_pas_disparaitre_les_operations():
    """Un périmètre agrégé peut ne pas porter la colonne. Renvoyer un DataFrame vide y
    supprimerait tout le bloc sans erreur ni message."""
    df = pd.DataFrame({"Taux de cofinancement": [0.55, 0.45]})
    plafonnees, ecartees = filtrer_fonds_plafonnes(df)

    assert len(plafonnees) == 2
    assert ecartees == 0
