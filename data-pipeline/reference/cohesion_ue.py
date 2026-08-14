"""
Catégorie de région au sens de la politique de cohésion UE 2021-2027.

Détermine le taux de cofinancement FEDER/FSE+ applicable (jusqu'à 85% en région moins
développée, 60% en transition, 50% en région plus développée) — c'est la donnée la plus
directement liée aux montants FEDER/FSE+/FTJ affichés dans le dashboard.

Source primaire : Commission Implementing Decision (EU) 2021/1130, Annexes I/II/III (liste
officielle par code NUTS2). Récupérée manuellement le 2026-08-14 (EUR-Lex bloque les
requêtes automatisées par un pare-feu anti-bot) :
  - Annexe I   (moins développées) : Guadeloupe, Guyane, La Réunion, Mayotte
  - Annexe II  (en transition)     : les 21 autres régions NUTS2 françaises, dont Martinique
  - Annexe III (plus développées)  : Île-de-France, Rhône-Alpes

NUTS2_CATEGORIE ci-dessous est donc au niveau des anciennes régions (voir nuts.py). Le
résultat exposé, REGION_CATEGORIE_UE, est agrégé vers les régions modernes via
region_mapping.OLD_NAME_TO_MODERN : un seul cas mixte, Auvergne-Rhône-Alpes, regroupe
Rhône-Alpes (plus développée) et Auvergne (en transition). Ce cas mixte est corroboré
indépendamment par programmes_2021_2027.py (Tableau 9B de l'Accord de partenariat 2021-2027) :
le programme "Auvergne-Rhône-Alpes..." y liste lui-même des lignes budgétaires FEDER et FSE+
séparées pour "Plus développée" et "En transition" au sein du même programme — et donne mieux
qu'une confirmation qualitative : la répartition € réelle entre les deux catégories. Pour tout
région mixte, _weighted_categorie_from_programmes() utilise donc cette répartition budgétaire
FEDER (proxy la plus directement liée à l'argent affiché dans le dashboard, plutôt qu'une
simple fusion géographique anciennes-régions) quand elle est disponible, avec repli sur le
libellé qualitatif sinon.

REGION_ULTRAPERIPHERIQUE (ajouté le 2026-08-14, source : programmes_2021_2027.py / Tableau
9B) : les 6 programmes DOM + Saint-Martin touchent, EN PLUS de leur enveloppe de catégorie de
région, une allocation additionnelle "Ultrapériphériques" (art. 349 TFUE, compensation d'un
handicap structurel permanent) — ce n'est pas une catégorie alternative à "moins développée",
mais une ligne budgétaire distincte au sein du même programme. Absent de la Commission
Implementing Decision 2021/1130 (qui ne couvre que les 3 catégories de cohésion), découvert
en croisant avec le Tableau 9B.

Saint-Martin n'apparaît dans aucune annexe de la décision 2021/1130 (pas de code NUTS2
propre, en dessous du seuil de population) : sa catégorie était laissée à None jusqu'au
2026-08-14, où le Tableau 9B (programme "Saint Martin FEDER 2021-2027", CCI 2021FR16RFPR001)
a montré une ligne budgétaire "Moins développée" + une ligne "Ultrapériphériques" — donc
"moins développée" est correct, tiré d'une source plus spécifique (le programme lui-même)
plutôt que de la liste générale par NUTS2.
"""

from region_mapping import OLD_NAME_TO_MODERN

from .nuts import NUTS2_CODE_TO_OLD_REGION
from .programmes_2021_2027 import PROGRAMMES

# Programmes ayant une ligne budgétaire "Ultrapériphériques" distincte dans le Tableau 9B
# (voir programmes_2021_2027.py) — allocation additionnelle RUP en plus de leur catégorie de
# région de base.
REGION_ULTRAPERIPHERIQUE = {"Guadeloupe", "Martinique", "Guyane", "La Réunion", "Mayotte", "Saint-Martin"}

NUTS2_CATEGORIE = {
    "FR10": "plus développée",
    "FRK2": "plus développée",
    "FRB0": "en transition",
    "FRC1": "en transition",
    "FRC2": "en transition",
    "FRD1": "en transition",
    "FRD2": "en transition",
    "FRE1": "en transition",
    "FRE2": "en transition",
    "FRF1": "en transition",
    "FRF2": "en transition",
    "FRF3": "en transition",
    "FRG0": "en transition",
    "FRH0": "en transition",
    "FRI1": "en transition",
    "FRI2": "en transition",
    "FRI3": "en transition",
    "FRJ1": "en transition",
    "FRJ2": "en transition",
    "FRK1": "en transition",
    "FRL0": "en transition",
    "FRM0": "en transition",
    "FRY2": "en transition",
    "FRY1": "moins développée",
    "FRY3": "moins développée",
    "FRY4": "moins développée",
    "FRY5": "moins développée",
}


def _weighted_categorie_from_programmes(modern_region, fonds="FEDER"):
    """Répartition € réelle (Tableau 9B) entre catégories pour une région à cheval sur
    plusieurs catégories NUTS2 — plus précise qu'une fusion géographique anciennes-régions
    car basée directement sur les enveloppes budgétaires FEDER du programme. None si le
    programme de cette région n'a pas de ligne multi-catégorie pour ce fonds (pas de repli
    silencieux vers un résultat trompeur : l'appelant retombe alors sur le libellé qualitatif)."""
    rows = [p for p in PROGRAMMES if p.region == modern_region and p.fonds == fonds and p.categorie]
    if len({p.categorie for p in rows}) < 2:
        return None
    total = sum(p.contribution_ue for p in rows)
    parts = sorted(rows, key=lambda p: -p.contribution_ue)
    detail = " / ".join(f"{p.contribution_ue / total:.0%} {p.categorie}" for p in parts)
    return f"Mixte : {detail} ({fonds})"


def _compute_modern_categories():
    modern_groups = {}
    for nuts_code, old_region in NUTS2_CODE_TO_OLD_REGION.items():
        modern_region = OLD_NAME_TO_MODERN[old_region]
        categorie = NUTS2_CATEGORIE[nuts_code]
        modern_groups.setdefault(modern_region, []).append((old_region, categorie))

    result = {}
    for modern_region, entries in modern_groups.items():
        categories = {categorie for _, categorie in entries}
        if len(categories) == 1:
            result[modern_region] = categories.pop()
        else:
            weighted = _weighted_categorie_from_programmes(modern_region)
            if weighted:
                result[modern_region] = weighted
            else:
                detail = ", ".join(f"{name} : {categorie}" for name, categorie in sorted(entries))
                result[modern_region] = f"mixte ({detail})"

    # Absent des annexes de la décision 2021/1130 (pas de code NUTS2 propre) mais confirmé
    # "moins développée" par le Tableau 9B (programme "Saint Martin FEDER 2021-2027") — voir
    # docstring du module.
    result["Saint-Martin"] = "moins développée"
    return result


REGION_CATEGORIE_UE = _compute_modern_categories()
