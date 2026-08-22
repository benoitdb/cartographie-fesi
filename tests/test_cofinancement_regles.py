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

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.cofinancement import bucket_categorie, plafond_categorie  # noqa: E402

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
