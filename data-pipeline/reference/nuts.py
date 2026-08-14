"""
Codes NUTS 2021 pour les régions françaises.

La Commission européenne utilise encore le découpage pré-réforme territoriale 2016 comme
niveau NUTS2 pour la France métropolitaine (Eurostat n'a pas adopté les régions fusionnées
"loi NOTRe" comme unités NUTS2) : une région moderne comme Grand Est ou Auvergne-Rhône-Alpes
peut donc regrouper plusieurs codes NUTS2 distincts. Voir region_mapping.OLD_NAME_TO_MODERN
pour la table de correspondance ancienne région → région moderne, et cohesion_ue.py pour un
exemple concret où cette distinction change le résultat (Auvergne-Rhône-Alpes).

Saint-Martin n'a pas de code NUTS2 propre (en dessous du seuil de population).
"""

NUTS2_CODE_TO_OLD_REGION = {
    "FR10": "Île-de-France",
    "FRB0": "Centre-Val de Loire",
    "FRC1": "Bourgogne",
    "FRC2": "Franche-Comté",
    "FRD1": "Basse-Normandie",
    "FRD2": "Haute-Normandie",
    "FRE1": "Nord-Pas-de-Calais",
    "FRE2": "Picardie",
    "FRF1": "Alsace",
    "FRF2": "Champagne-Ardenne",
    "FRF3": "Lorraine",
    "FRG0": "Pays de la Loire",
    "FRH0": "Bretagne",
    "FRI1": "Aquitaine",
    "FRI2": "Limousin",
    "FRI3": "Poitou-Charentes",
    "FRJ1": "Languedoc-Roussillon",
    "FRJ2": "Midi-Pyrénées",
    "FRK1": "Auvergne",
    "FRK2": "Rhône-Alpes",
    "FRL0": "Provence-Alpes-Côte d'Azur",
    "FRM0": "Corse",
    "FRY1": "Guadeloupe",
    "FRY2": "Martinique",
    "FRY3": "Guyane",
    "FRY4": "La Réunion",
    "FRY5": "Mayotte",
}
