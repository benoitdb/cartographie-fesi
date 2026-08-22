"""
Harmonisation des régions : mapping pré-2016 → modernes (loi NOTRE).

Tables de référence pour normaliser les valeurs hétérogènes du fichier source :
- codes INSEE régions anciennes → noms modernes (uniquement les codes confirmés
  contre les données réelles — voir OLD_NAME_TO_MODERN pour le filet de sécurité)
- noms d'anciennes régions → noms modernes (filet de sécurité par nom : le champ
  source associe toujours un nom à son code, "CODE/Nom", donc un code jamais vu
  jusqu'ici reste résolu correctement via son nom)
- libellés mal orthographiés → formes canoniques
- programmes régionaux → région unique (fallback quand région manquante)

Le fichier source provient à chaque export du même système national et présente
des particularités récurrentes (codes anciens ET modernes mélangés, libellés à
variantes, valeur sentinelle "Volet national" au lieu d'un champ vide) : la
fonction harmonize_region est conçue pour rester correcte même face à un code
jamais rencontré, et pour signaler explicitement (via UNRESOLVED_FRAGMENTS) tout
fragment qu'elle n'a pas pu résoudre, plutôt que de le laisser passer en silence.
"""

import pandas as pd

# Régions modernes valides (13 métropole + DOM + Saint-Martin) — sert à repérer les
# fragments bruts déjà "modernes" et à valider les résolutions par nom.
MODERN_REGIONS = {
    'Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', 'Bretagne', 'Centre-Val de Loire', 'Corse',
    'Grand Est', 'Hauts-de-France', 'Île-de-France', 'Normandie', 'Nouvelle-Aquitaine', 'Occitanie',
    'Pays de la Loire', 'Provence-Alpes-Côte d\'Azur',
    'Guadeloupe', 'Martinique', 'Guyane', 'La Réunion', 'Mayotte', 'Saint-Martin',
}

# Code INSEE région (pré ou post-2016, format "CODE/Nom" du champ source) → nom région
# moderne. Volontairement restreint aux codes confirmés en croisant ce dictionnaire
# avec l'intégralité des valeurs réellement présentes dans le fichier source (aucune
# entrée "au cas où" non vérifiable) — les codes 06 excepté (Mayotte, DOM absent des
# données actuelles mais suit la même série que 01-04, confirmés).
OLD_TO_MODERN = {
    # DOM
    '01': 'Guadeloupe',
    '02': 'Martinique',
    '03': 'Guyane',
    '04': 'La Réunion',
    '06': 'Mayotte',

    # Métropole
    '11': 'Île-de-France',
    '21': 'Grand Est',                    # ex-Champagne-Ardenne
    '22': 'Hauts-de-France',              # ex-Picardie
    '24': 'Centre-Val de Loire',
    '26': 'Bourgogne-Franche-Comté',      # ex-Bourgogne
    '27': 'Bourgogne-Franche-Comté',
    '28': 'Normandie',
    '31': 'Hauts-de-France',              # ex-Nord-Pas-de-Calais
    '32': 'Hauts-de-France',
    '41': 'Grand Est',                    # ex-Lorraine
    '42': 'Grand Est',                    # ex-Alsace
    '43': 'Bourgogne-Franche-Comté',      # ex-Franche-Comté
    '44': 'Grand Est',
    '52': 'Pays de la Loire',
    '53': 'Bretagne',
    '73': 'Occitanie',                    # ex-Midi-Pyrénées
    '76': 'Occitanie',
    '82': 'Auvergne-Rhône-Alpes',         # ex-Rhône-Alpes
    '83': 'Auvergne-Rhône-Alpes',         # ex-Auvergne
    '84': 'Auvergne-Rhône-Alpes',
    '93': 'Provence-Alpes-Côte d\'Azur',
    '94': 'Corse',
}

# Filet de sécurité par nom : noms d'anciennes régions (réforme territoriale de 2016,
# fait public bien établi) → région moderne, plus une identité pour les régions
# inchangées. Utilisé quand le code du fragment "CODE/Nom" n'est pas (ou pas encore)
# dans OLD_TO_MODERN — le nom associé au code dans la donnée source permet de
# résoudre correctement sans dépendre d'un code jamais vérifié.
OLD_NAME_TO_MODERN = {
    'Alsace': 'Grand Est',
    'Champagne-Ardenne': 'Grand Est',
    'Lorraine': 'Grand Est',
    'Aquitaine': 'Nouvelle-Aquitaine',
    'Limousin': 'Nouvelle-Aquitaine',
    'Poitou-Charentes': 'Nouvelle-Aquitaine',
    'Bourgogne': 'Bourgogne-Franche-Comté',
    'Franche-Comté': 'Bourgogne-Franche-Comté',
    'Basse-Normandie': 'Normandie',
    'Haute-Normandie': 'Normandie',
    'Languedoc-Roussillon': 'Occitanie',
    'Midi-Pyrénées': 'Occitanie',
    'Nord-Pas-de-Calais': 'Hauts-de-France',
    'Picardie': 'Hauts-de-France',
    'Auvergne': 'Auvergne-Rhône-Alpes',
    'Rhône-Alpes': 'Auvergne-Rhône-Alpes',
    # Régions inchangées par la réforme (identité, pour homogénéiser la résolution par nom)
    'Bretagne': 'Bretagne',
    'Centre': 'Centre-Val de Loire',
    'Centre-Val de Loire': 'Centre-Val de Loire',
    'Corse': 'Corse',
    'Île-de-France': 'Île-de-France',
    'Ile-de-France': 'Île-de-France',
    'Pays de la Loire': 'Pays de la Loire',
    'Provence-Alpes-Côte d\'Azur': 'Provence-Alpes-Côte d\'Azur',
    'Guadeloupe': 'Guadeloupe',
    'Martinique': 'Martinique',
    'Guyane': 'Guyane',
    'Réunion': 'La Réunion',
    'La Réunion': 'La Réunion',
    'Mayotte': 'Mayotte',
}

# Libellés déjà "modernes" mais mal orthographiés → forme canonique (pour GeoJSON matching)
NORMALIZE_BARE = {
    'Ile-de-France': 'Île-de-France',
    'Provence - Alpes - Côte d\'azur': 'Provence-Alpes-Côte d\'Azur',
    'Provence-Alpes-Cote d\'Azur': 'Provence-Alpes-Côte d\'Azur',
}

# Valeur sentinelle observée dans le champ source à la place d'un champ vide : à traiter
# comme "pas de région" (national), pas comme un nom de région à part entière.
VOLET_NATIONAL_LABEL = 'volet national'

# Programmes régionaux : libellé exact → région unique
# Vérifié exhaustif vs. les 21 programmes réellement présents
PROGRAMME_TO_REGION = {
    'Programme Bretagne FEDER-FSE+ 2021-2027': 'Bretagne',
    'Programme Centre-Val de Loire et interrégional Loire FEDER-FSE+ 2021-2027': 'Centre-Val de Loire',
    'Programme Corse FEDER-FSE+ 2021-2027': 'Corse',
    'Programme FEDER FSE+ Nouvelle-Aquitaine': 'Nouvelle-Aquitaine',
    'Programme FEDER-FSE+ 2021-2027 de La Réunion': 'La Réunion',
    'Programme FEDER-FSE+ Auvergne-Rhône-Alpes 2021-2027': 'Auvergne-Rhône-Alpes',
    'Programme FEDER-FSE+ Bourgogne Franche-Comté et Massif du Jura 2021-2027': 'Bourgogne-Franche-Comté',
    'Programme FEDER-FSE+ GUYANE 2021-2027': 'Guyane',
    'Programme FEDER-FSE+ Guadeloupe 2021-2027': 'Guadeloupe',
    'Programme Grand Est et massif des Vosges FEDER-FSE+-FTJ 2021-2027': 'Grand Est',
    'Programme Hauts de France FEDER-FSE+-FTJ 2021-2027': 'Hauts-de-France',
    'Programme Martinique FEDER-FSE+ 2021-2027': 'Martinique',
    'Programme Mayotte  FEDER-FSE+ 2021- 2027': 'Mayotte',
    'Programme Normandie FEDER-FSE+-FTJ 2021-2027': 'Normandie',
    'Programme Occitanie FEDER-FSE+ 2021- 2027': 'Occitanie',
    'Programme Pays de la Loire  FEDER-FSE+-FTJ 2021-2027': 'Pays de la Loire',
    'Programme Provence-Alpes-Côte d\'Azur et Massif des Alpes FEDER-FSE+-FTJ 2021-2027': 'Provence-Alpes-Côte d\'Azur',
    'Programme régional Île-de-France et bassin de la Seine FEDER-FSE+ 2021-2027': 'Île-de-France',
    'Programme Saint Martin FEDER 2021-2027': 'Saint-Martin',
    # Programmes nationaux sont volontairement absents — pas de fallback région unique
}

# Fragments bruts que ni le code, ni le nom, ni la normalisation n'ont su résoudre avec
# certitude (résolus quand même via le nom brut, en dernier recours, pour ne pas faire
# planter le pipeline) — à examiner après chaque ingestion : reset_unresolved() puis
# get_unresolved() une fois le pipeline passé sur tout le fichier.
UNRESOLVED_FRAGMENTS = []


def reset_unresolved():
    UNRESOLVED_FRAGMENTS.clear()


def get_unresolved():
    return list(UNRESOLVED_FRAGMENTS)


def _resolve_named_fragment(code, name):
    """Résout un fragment "CODE/Nom" : priorité au code (rapide, vérifié), repli sur le
    nom (toujours fiable, fait public) si le code est inconnu. Retourne (region, résolu)."""
    region = OLD_TO_MODERN.get(code)
    if region:
        return region, True
    region = OLD_NAME_TO_MODERN.get(name)
    if region:
        return region, True
    return name, False


def harmonize_region(raw_region, libelle_programme):
    """
    Normalise une valeur région brute en liste de régions modernes.

    Args:
        raw_region (str or None): Valeur brute du champ "Région de l'opération"
        libelle_programme (str): Libellé du programme (pour fallback si région vide)

    Returns:
        tuple: (regions_modernes: list[str], is_interregional: bool, is_national: bool)
            - regions_modernes: liste triée de noms de régions harmonisées
            - is_interregional: True si >1 région unique après déduplication
            - is_national: True si l'opération n'est rattachée à aucune région (Volet national)
    """

    # Cas 1 : région manquante
    if not raw_region or (isinstance(raw_region, float) and pd.isna(raw_region)):
        # Fallback via le programme si c'est un programme régional
        if libelle_programme in PROGRAMME_TO_REGION:
            region = PROGRAMME_TO_REGION[libelle_programme]
            return ([region], False, False)
        # Sinon : Volet national ou programme national sans région
        return ([], False, True)

    # Cas 2 : région présente → parser et normaliser
    raw_region = str(raw_region).strip()

    # Split sur `|` (plusieurs régions)
    fragments = [f.strip() for f in raw_region.split('|')]
    fragments = [f for f in fragments if f]  # retirer les fragments vides

    regions_modernes = set()
    had_volet_national = False

    for fragment in fragments:
        if fragment.lower() == VOLET_NATIONAL_LABEL:
            # Valeur sentinelle : pas une région, traité après la boucle
            had_volet_national = True
            continue

        if '/' in fragment:
            # Format "CODE/Nom" → extraire le code, résoudre (code puis nom)
            code, name = fragment.split('/', 1)
            code = code.strip()
            name = name.strip()
            region, resolved = _resolve_named_fragment(code, name)
            if not resolved:
                UNRESOLVED_FRAGMENTS.append(fragment)
            regions_modernes.add(region)
        else:
            # Format bare "Nom" → normaliser orthographe
            normalized = NORMALIZE_BARE.get(fragment, fragment)
            if normalized not in MODERN_REGIONS:
                # Nom bare non reconnu : tenter la résolution par ancien nom, sinon signaler
                resolved_name = OLD_NAME_TO_MODERN.get(normalized)
                if resolved_name:
                    normalized = resolved_name
                else:
                    UNRESOLVED_FRAGMENTS.append(fragment)
            regions_modernes.add(normalized)

    # Une opération dont tous les fragments sont "Volet national" est nationale, pas
    # régionale ; combinée à de vraies régions (cas non observé à ce jour mais possible),
    # on garde les régions et on ignore juste la mention "Volet national".
    if had_volet_national and not regions_modernes:
        return ([], False, True)

    regions_modernes = sorted(regions_modernes)

    # Déterminer si interrégional
    is_interregional = len(regions_modernes) > 1
    is_national = False  # On n'arrive ici que si région était présente

    return (regions_modernes, is_interregional, is_national)

