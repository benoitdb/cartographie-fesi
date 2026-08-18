import re

# Taux de cofinancement UE maximal par catégorie de région (politique de cohésion 2021-2027,
# règlement (UE) 2021/1060, art. 112) : 85% moins développée, 60% en transition, 50% plus
# développée. Les régions ultrapériphériques (RUP, art. 349 TFUE) bénéficient du plafond le
# plus élevé (85%) quelle que soit leur catégorie de base — voir cohesion_ue.py.
PLAFOND_PAR_CATEGORIE = {
    "plus développée": 0.50,
    "en transition": 0.60,
    "moins développée": 0.85,
}
PLAFOND_RUP = 0.85

# Regex pour les catégories mixtes telles que transcrites dans region_metadata.json (voir
# cohesion_ue.py _weighted_categorie_from_programmes) : "Mixte : 57% Plus développée / 43%
# En transition (FEDER)".
_MIXTE_PART_RE = re.compile(r"(\d+)%\s*([^/(]+)")


def plafond_categorie(categorie_ue, ultraperipherique=False):
    """Taux de cofinancement UE maximal applicable, ou None si la catégorie est absente/non
    reconnue. Une région ultrapériphérique a toujours 85%, indépendamment de sa catégorie de
    base. Une catégorie mixte (ex. Auvergne-Rhône-Alpes) retourne la moyenne pondérée des
    plafonds de chaque catégorie composante, au prorata des poids transcrits dans le libellé."""
    if ultraperipherique:
        return PLAFOND_RUP
    if not categorie_ue:
        return None

    categorie_lower = categorie_ue.strip().lower()
    if categorie_lower in PLAFOND_PAR_CATEGORIE:
        return PLAFOND_PAR_CATEGORIE[categorie_lower]

    poids_total, plafond_pondere = 0, 0.0
    for poids_str, label in _MIXTE_PART_RE.findall(categorie_ue):
        rate = PLAFOND_PAR_CATEGORIE.get(label.strip().lower())
        if rate is None:
            continue
        poids = int(poids_str)
        poids_total += poids
        plafond_pondere += poids * rate
    return plafond_pondere / poids_total if poids_total else None


def bucket_categorie(categorie_ue, ultraperipherique=False):
    """Regroupe une région dans un intitulé de catégorie affichable (pour agréger plusieurs
    régions ensemble, ex. graphe national par catégorie) : les 3 catégories de cohésion
    telles quelles, "+ RUP" ajouté si ultrapériphérique, "Mixte" pour les régions à cheval sur
    deux catégories (transcrites avec un libellé "Mixte : ...")."""
    if not categorie_ue:
        return "Non classifiée"
    categorie_lower = categorie_ue.strip().lower()
    if categorie_lower in PLAFOND_PAR_CATEGORIE:
        label = categorie_ue.strip().capitalize()
    elif categorie_lower.startswith("mixte"):
        label = "Mixte"
    else:
        label = categorie_ue.strip()
    return f"{label} + RUP" if ultraperipherique else label
