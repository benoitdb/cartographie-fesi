"""Régions couvertes par les 5 programmes opérationnels interrégionaux FEDER 2014-2020.

Source : pages officielles ec.europa.eu par programme (DG REGIO, "in your country"),
une page par CCI, consultées le 2026-08-28 :
https://ec.europa.eu/regional_policy/in-your-country/programmes/2014-2020/fr/<cci minuscule>_fr

Chaque page donne le nom exact du programme et l'énumération des "régions
administratives" (cadre 2014, avant la fusion des régions de 2016) qu'il couvre —
converties ici en régions modernes via region_mapping.OLD_NAME_TO_MODERN. Un
recoupement contre reference/programmes_2014_2020.py a confirmé un montant déjà
transcrit (POI Pyrénées, FEDER 24 872 998 €, identique entre l'Accord de
partenariat et la page EC).

Un programme interrégional couvre plusieurs régions par construction — c'est
justement l'objet d'un massif ou d'un bassin fluvial, pas une région administrative.
Cette table sert à ROUTER ses opérations vers un périmètre "Interrégional" à part
(issue #77), PAS à VENTILER leur montant entre les régions listées : aucune donnée
ne dit quelle part revient à laquelle, une répartition inventée serait pire que de
les compter à part (choix déjà tranché dans l'issue).

Clés : libellés Synergie exacts, identiques à ceux de
region_mapping.PROGRAMME_TO_REGION_2014_2020 (où ces 5 programmes valent None) — pas
les noms courts de l'Accord de partenariat (ex. "POI Alpes"), qui diffèrent.
"""

REGIONS_PAR_PROGRAMME_INTERREGIONAL_2014_2020 = {
    # CCI 2014FR16RFOP001 — .../2014fr16rfop001_fr — budget 68 M€ (34 M€ FEDER)
    'Programme opérationnel Interrégional FEDER du Massif des Alpes 2014-2020': [
        'Auvergne-Rhône-Alpes', "Provence-Alpes-Côte d'Azur",
    ],
    # CCI 2014FR16RFOP002 — .../2014fr16rfop002_fr — budget 73,8 M€ (40,8 M€ FEDER)
    'Programme opérationnel Interrégional FEDER Loire 2014-2020': [
        'Centre-Val de Loire', 'Normandie', 'Bourgogne-Franche-Comté',
        'Pays de la Loire', 'Nouvelle-Aquitaine', 'Auvergne-Rhône-Alpes', 'Occitanie',
    ],
    # CCI 2014FR16RFOP003 — .../2014fr16rfop003_fr — budget 78,3 M€ (38,6 M€ FEDER)
    'Programme opérationnel interrégionnal Massif Central FEDER 2014-2020': [
        'Bourgogne-Franche-Comté', 'Occitanie', 'Nouvelle-Aquitaine', 'Auvergne-Rhône-Alpes',
    ],
    # CCI 2014FR16RFOP004 — .../2014fr16rfop004_fr — budget 49,7 M€ (24,9 M€ FEDER)
    'Programme opérationnel Interrégional FEDER Pyrénées 2014-2020': [
        'Nouvelle-Aquitaine', 'Occitanie',
    ],
    # CCI 2014FR16RFOP005 — .../2014fr16rfop005_fr — budget 66 M€ (33 M€ FEDER)
    'Programme opérationnel Interrégional FEDER Rhône-Saône 2014-2020': [
        'Auvergne-Rhône-Alpes', "Provence-Alpes-Côte d'Azur", 'Occitanie', 'Bourgogne-Franche-Comté',
    ],
}
