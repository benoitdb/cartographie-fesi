"""
Codes NUTS2010 pour les régions françaises — période 2014-2020.

La Commission Implementing Decision 2014/99/UE (liste des régions par catégorie de
cohésion, voir cohesion_ue_2014_2020.py) utilise la nomenclature NUTS2010, distincte de
la NUTS2021 utilisée par nuts.py pour 2021-2027 : les deux schémas diffèrent pour la
France. Île-de-France reste FR10 dans les deux, mais la plupart des autres régions
changent de code (ex. Picardie : FR22 en NUTS2010, FRE2 en NUTS2021) — cette table ne se
substitue pas à nuts.py, elle le complète pour la période antérieure.

Ancienne région (pré-réforme 2016) : mêmes libellés que nuts.py et
region_mapping.OLD_NAME_TO_MODERN, pour rester agrégeable vers les régions modernes par
la même table.
"""

NUTS2010_CODE_TO_OLD_REGION = {
    "FR10": "Île-de-France",
    "FR21": "Champagne-Ardenne",
    "FR22": "Picardie",
    "FR23": "Haute-Normandie",
    "FR24": "Centre",
    "FR25": "Basse-Normandie",
    "FR26": "Bourgogne",
    "FR30": "Nord-Pas-de-Calais",
    "FR41": "Lorraine",
    "FR42": "Alsace",
    "FR43": "Franche-Comté",
    "FR51": "Pays de la Loire",
    "FR52": "Bretagne",
    "FR53": "Poitou-Charentes",
    "FR61": "Aquitaine",
    "FR62": "Midi-Pyrénées",
    "FR63": "Limousin",
    "FR71": "Rhône-Alpes",
    "FR72": "Auvergne",
    "FR81": "Languedoc-Roussillon",
    "FR82": "Provence-Alpes-Côte d'Azur",
    "FR83": "Corse",
    "FR91": "Guadeloupe",
    "FR92": "Martinique",
    "FR93": "Guyane",
    "FR94": "Réunion",
    "FR-": "Mayotte",  # Pas de code NUTS2010 propre (en dessous du seuil de population)
}
