"""
Catégorie de région au sens de la politique de cohésion UE 2014-2020.

Détermine le taux de cofinancement FEDER/FSE applicable pour la période (art. 120 du
règlement (UE) n° 1303/2013 : 85% Fonds de cohésion et régions moins développées, 60% en
transition, 50% plus développées — voir dashboard/utils/cofinancement.py pour
l'application de ces plafonds). Le fonds REACT-EU y déroge explicitement (règlement (UE)
2020/2221, art. 92 ter §12 : jusqu'à 100%, quelle que soit la catégorie de région) — ce
module ne le couvre pas, une opération REACT-EU ne doit jamais être évaluée contre
PLAFOND_PAR_CATEGORIE.

Source primaire : Commission Implementing Decision 2014/99/UE, Annexes I/II/III (liste
officielle par code NUTS2010 — voir nuts_2014_2020.py pour la distinction avec la
NUTS2021 utilisée en 2021-2027). Récupérée manuellement le 2026-08-25 (EUR-Lex bloque les
requêtes automatisées, comme pour 2021/1130 en 21-27) :
  - Annexe I   (moins développées) : Guadeloupe, Martinique, Guyane, Réunion, Mayotte
  - Annexe II  (en transition)     : 10 régions métropolitaines — Picardie, Basse-Normandie,
    Nord-Pas-de-Calais, Lorraine, Franche-Comté, Poitou-Charentes, Limousin, Auvergne,
    Languedoc-Roussillon, Corse
  - Annexe III (plus développées)  : 12 régions métropolitaines — Île-de-France,
    Champagne-Ardenne, Haute-Normandie, Centre, Bourgogne, Alsace, Pays de la Loire,
    Bretagne, Aquitaine, Midi-Pyrénées, Rhône-Alpes, Provence-Alpes-Côte d'Azur

Voir docs/sources/decision_2014_99_categories_region.md pour le détail des trois annexes.

NUTS2010_CODE_TO_OLD_REGION ci-dessous est donc au niveau des anciennes régions. Le
résultat exposé, REGION_CATEGORIE_UE_2014_2020, est agrégé vers les régions modernes via
region_mapping.OLD_NAME_TO_MODERN — avec **6 cas mixtes** (contre 1 seul en 2021-2027,
Auvergne-Rhône-Alpes) : Grand Est, Bourgogne-Franche-Comté, Nouvelle-Aquitaine,
Occitanie, Auvergne-Rhône-Alpes, Normandie. Hauts-de-France est homogène malgré la
fusion (Nord-Pas-de-Calais + Picardie, toutes deux en transition).

Contrairement à 2021-2027, où le Tableau 9B de l'Accord de partenariat donne pour les
régions mixtes des lignes budgétaires FEDER séparées par catégorie au sein d'un même
programme (permettant une pondération par répartition € réelle, voir
cohesion_ue._weighted_categorie_from_programmes), la structure 2014-2020 est différente :
un programme par ANCIENNE région, chacun mono-catégorie (ex. "PO FEDER-FSE Rhône-Alpes
2014-2020" et "Programme opérationnel régional Auvergne FEDER-FSE 2014-2020" sont deux
programmes distincts — voir region_mapping.PROGRAMME_TO_REGION_2014_2020). Une
pondération par dotation réelle par programme resterait possible en reprenant la table
de l'Accord de partenariat 2014-2020 (docs/sources/accord_partenariat_2014_2020.md), mais
n'est pas faite ici : ce module s'en tient au repli qualitatif (détail par ancienne
région, sans pondération), qui est déjà le comportement de repli existant en 2021-2027
quand aucune donnée budgétaire n'est disponible. Amélioration possible, non bloquante
pour #81 (le plafond de cofinancement n'a besoin que de savoir si une région est
mono-catégorie ou mixte, pas de la pondération exacte — voir bucket_categorie côté
dashboard).

Aucune région française n'a de dotation "Ultrapériphériques" distincte identifiée dans ce
module pour 2014-2020 (contrairement à 2021-2027, où le Tableau 9B l'isole) : les DROM
sont "moins développées" tout court ici. Pas une omission — l'Accord de partenariat
2014-2020 ne isole pas cette ligne budgétaire de la même façon dans les tableaux
consultés (docs/sources/accord_partenariat_2014_2020.md) ; à revoir si un jour cette
distinction s'avère nécessaire pour la période.
"""

from region_mapping import OLD_NAME_TO_MODERN

from .nuts_2014_2020 import NUTS2010_CODE_TO_OLD_REGION

NUTS2010_CATEGORIE = {
    # Annexe I — moins développées
    "FR91": "moins développée",
    "FR92": "moins développée",
    "FR93": "moins développée",
    "FR94": "moins développée",
    "FR-": "moins développée",
    # Annexe II — en transition
    "FR22": "en transition",
    "FR25": "en transition",
    "FR30": "en transition",
    "FR41": "en transition",
    "FR43": "en transition",
    "FR53": "en transition",
    "FR63": "en transition",
    "FR72": "en transition",
    "FR81": "en transition",
    "FR83": "en transition",
    # Annexe III — plus développées
    "FR10": "plus développée",
    "FR21": "plus développée",
    "FR23": "plus développée",
    "FR24": "plus développée",
    "FR26": "plus développée",
    "FR42": "plus développée",
    "FR51": "plus développée",
    "FR52": "plus développée",
    "FR61": "plus développée",
    "FR62": "plus développée",
    "FR71": "plus développée",
    "FR82": "plus développée",
}


def _compute_modern_categories():
    modern_groups = {}
    for nuts_code, old_region in NUTS2010_CODE_TO_OLD_REGION.items():
        modern_region = OLD_NAME_TO_MODERN[old_region]
        categorie = NUTS2010_CATEGORIE[nuts_code]
        modern_groups.setdefault(modern_region, []).append((old_region, categorie))

    result = {}
    for modern_region, entries in modern_groups.items():
        categories = {categorie for _, categorie in entries}
        if len(categories) == 1:
            result[modern_region] = categories.pop()
        else:
            detail = ", ".join(f"{name} : {categorie}" for name, categorie in sorted(entries))
            result[modern_region] = f"mixte ({detail})"
    return result


REGION_CATEGORIE_UE_2014_2020 = _compute_modern_categories()
