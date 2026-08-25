"""Catégories de région 2014-2020 (issue #81) — transcription de la décision 2014/99/UE.

Ce que ces tests protègent n'est pas un calcul mais une **transcription**, et une
transcription fausse ne lève rien : elle déplace le plafond de cofinancement affiché pour
une région, ce qui fait passer des opérations pour conformes, ou l'inverse.

Deux risques distincts :

1. **le rattachement ancienne région → catégorie**, saisi depuis les annexes I/II/III de la
   décision — vérifié ici sur les invariants publiés (nombre de régions par annexe) plutôt
   que ligne à ligne, un test qui recopierait la table ne ferait que la dupliquer ;
2. **l'agrégation vers les régions modernes**, qui est le vrai piège de la période : six
   régions modernes réunissent des anciennes régions de catégories différentes, contre une
   seule en 2021-2027. Une agrégation qui écraserait silencieusement l'une des deux
   catégories donnerait un plafond unique là où il n'en existe pas.
"""

import json
from pathlib import Path

from categories_ue_2014_2020 import OUTPUT_PATH, construire

from reference.cohesion_ue_2014_2020 import NUTS2010_CATEGORIE
from reference.nuts_2014_2020 import NUTS2010_CODE_TO_OLD_REGION

# Les six régions modernes à cheval sur deux catégories de l'époque. Posées en dur : c'est
# le fait que l'issue #81 devait établir, et le voir changer doit demander une décision, pas
# passer inaperçu.
REGIONS_MIXTES = {
    "Auvergne-Rhône-Alpes",
    "Bourgogne-Franche-Comté",
    "Grand Est",
    "Normandie",
    "Nouvelle-Aquitaine",
    "Occitanie",
}


def test_les_effectifs_des_trois_annexes_sont_ceux_de_la_decision():
    """Décision 2014/99/UE : 5 régions moins développées (les DROM), 10 en transition,
    12 plus développées. Un code NUTS rangé dans la mauvaise annexe change ces effectifs."""
    effectifs = {}
    for categorie in NUTS2010_CATEGORIE.values():
        effectifs[categorie] = effectifs.get(categorie, 0) + 1

    assert effectifs == {"moins développée": 5, "en transition": 10, "plus développée": 12}


def test_chaque_ancienne_region_a_une_categorie_et_une_seule():
    """Les deux tables sont saisies séparément : un code présent dans l'une et absent de
    l'autre ferait disparaître une ancienne région de l'agrégation, sans erreur."""
    assert set(NUTS2010_CODE_TO_OLD_REGION) == set(NUTS2010_CATEGORIE)


def test_les_six_regions_mixtes_sont_exactement_celles_attendues():
    """Le cœur de la période. Une septième région mixte, ou une sixième disparue, signale
    soit une erreur d'annexe, soit un changement dans la table de fusion des régions."""
    sortie = construire()
    mixtes = {region for region, infos in sortie.items() if infos["categorie_ue"] is None}

    assert mixtes == REGIONS_MIXTES


def test_une_region_mixte_n_a_pas_de_categorie_unique_mais_garde_ses_composantes():
    """`categorie_ue: None` et non un libellé « mixte » à parser : la catégorie n'existe pas
    à cette maille. Les composantes, elles, restent — sans elles le dashboard ne pourrait
    afficher ni fourchette de plafonds ni explication."""
    normandie = construire()["Normandie"]

    assert normandie["categorie_ue"] is None
    assert normandie["composantes"] == [
        ["Basse-Normandie", "en transition"],
        ["Haute-Normandie", "plus développée"],
    ]


def test_une_region_homogene_garde_aussi_ses_composantes():
    """Toujours renseignées, y compris quand elles s'accordent : l'appelant ne doit pas avoir
    à traiter deux formes de sortie selon l'homogénéité de la région."""
    hauts_de_france = construire()["Hauts-de-France"]

    assert hauts_de_france["categorie_ue"] == "en transition"
    assert hauts_de_france["composantes"] == [
        ["Nord-Pas-de-Calais", "en transition"],
        ["Picardie", "en transition"],
    ]


def test_le_fichier_committe_correspond_au_code_qui_le_produit():
    """Le JSON est committé (le dashboard le lit sans lancer le pipeline) : il peut donc
    dériver de la table qu'il transcrit sans que rien ne le signale. C'est le seul test qui
    attrape un fichier oublié après une correction de la décision 2014/99."""
    committe = json.loads(Path(OUTPUT_PATH).read_text(encoding="utf-8"))

    assert committe == construire()
