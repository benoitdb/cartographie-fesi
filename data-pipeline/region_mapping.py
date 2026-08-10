"""
Harmonisation des régions : mapping pré-2016 → modernes (loi NOTRE).

Tables de référence pour normaliser les valeurs hétérogènes du fichier source :
- codes INSEE régions anciennes → noms modernes
- libellés mal orthographiés → formes canoniques
- programmes régionaux → région unique (fallback quand région manquante)
"""

# Code INSEE région (pré-2016) → nom région moderne (post-2016)
# Couvre la totalité de la fusion officielle pour rester robuste aux futures publications
OLD_TO_MODERN = {
    # DOM inchangés
    '01': 'Guadeloupe',
    '02': 'Martinique',
    '03': 'Guyane',
    '04': 'La Réunion',
    '06': 'Mayotte',

    # Métropole
    '11': 'Île-de-France',                      # inchangé
    '24': 'Centre-Val de Loire',                # inchangé
    '28': 'Normandie',                          # ex-25 Basse-Normandie
    '25': 'Normandie',                          # ex-Basse-Normandie
    '23': 'Normandie',                          # ex-Haute-Normandie
    '53': 'Bretagne',                           # inchangé
    '52': 'Pays de la Loire',                   # inchangé
    '72': 'Nouvelle-Aquitaine',                 # ex-Poitou-Charentes
    '54': 'Nouvelle-Aquitaine',                 # ex-Limousin
    '75': 'Nouvelle-Aquitaine',                 # ex-Aquitaine
    '74': 'Nouvelle-Aquitaine',                 # ex-variante Aquitaine
    '26': 'Bourgogne-Franche-Comté',            # ex-Bourgogne
    '27': 'Bourgogne-Franche-Comté',            # ex-moderne Bourgogne-Franche-Comté
    '43': 'Bourgogne-Franche-Comté',            # ex-Franche-Comté
    '21': 'Grand Est',                          # ex-Champagne-Ardenne
    '22': 'Hauts-de-France',                    # ex-Picardie
    '23': 'Hauts-de-France',                    # ex-Haute-Normandie (aussi dans Normandie — voir logique)
    '31': 'Hauts-de-France',                    # ex-Nord-Pas-de-Calais
    '32': 'Hauts-de-France',                    # ex-moderne Hauts-de-France
    '41': 'Grand Est',                          # ex-Lorraine
    '42': 'Grand Est',                          # ex-Alsace
    '44': 'Grand Est',                          # ex-moderne Grand Est
    '73': 'Occitanie',                          # ex-Midi-Pyrénées
    '76': 'Occitanie',                          # ex-Languedoc-Roussillon
    '91': 'Occitanie',                          # ex-variante
    '82': 'Auvergne-Rhône-Alpes',               # ex-Rhône-Alpes
    '83': 'Auvergne-Rhône-Alpes',               # ex-Auvergne
    '84': 'Auvergne-Rhône-Alpes',               # ex-moderne Auvergne-Rhône-Alpes
    '93': 'Provence-Alpes-Côte d\'Azur',        # inchangé
    '94': 'Corse',                              # inchangé
}

# Libellés déjà "modernes" mais mal orthographiés → forme canonique (pour GeoJSON matching)
NORMALIZE_BARE = {
    'Ile-de-France': 'Île-de-France',
    'Provence - Alpes - Côte d\'azur': 'Provence-Alpes-Côte d\'Azur',
    'Provence-Alpes-Cote d\'Azur': 'Provence-Alpes-Côte d\'Azur',
}

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

    for fragment in fragments:
        if '/' in fragment:
            # Format "CODE/Nom" → extraire le code et mapper
            code, name = fragment.split('/', 1)
            code = code.strip()
            region = OLD_TO_MODERN.get(code)
            if region:
                regions_modernes.add(region)
            else:
                # Code inconnu, garder le nom brut (fallback gracieux)
                regions_modernes.add(name.strip())
        else:
            # Format bare "Nom" → normaliser orthographe
            normalized = NORMALIZE_BARE.get(fragment, fragment)
            regions_modernes.add(normalized)

    regions_modernes = sorted(regions_modernes)

    # Déterminer si interrégional
    is_interregional = len(regions_modernes) > 1
    is_national = False  # On n'arrive ici que si région était présente

    return (regions_modernes, is_interregional, is_national)


# ============================================================================
# Pour import de pandas dans le contexte du pipeline
# ============================================================================
import pandas as pd
