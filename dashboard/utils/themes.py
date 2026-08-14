"""Couleurs fixes par objectif stratégique (politique de cohésion UE 2021-2027), pour une
identité visuelle cohérente entre les treemaps et box plots qui les affichent (national +
régional) — au lieu d'une palette assignée par ordre d'apparition, qui varie selon le sous-
ensemble de données affiché."""

OBJECTIF_STRATEGIQUE_COLORS = {
    "1. Europe plus intelligente": "#4C72B0",  # bleu — innovation, numérique
    "2. Europe plus verte": "#55A868",  # vert — transition écologique
    "3. Europe plus connectée": "#64B5CD",  # bleu ciel — mobilité, réseaux
    "4. Europe plus sociale": "#8172B2",  # violet — emploi, inclusion, éducation
    "5. Europe plus proche des citoyens": "#DD8452",  # orange — développement territorial
    "8. Transition juste": "#937860",  # brun/doré — transition juste
    "Non spécifié": "#B0B0B0",
}

# Couleurs fixes par fonds (FEDER/FSE+/FTJ), même principe que OBJECTIF_STRATEGIQUE_COLORS —
# évite qu'un même fonds change de couleur d'un graphe à l'autre selon l'ordre d'apparition
# (trompeur). Palette catégorielle validée CVD-safe (voir skill dataviz), slots 1-3.
FONDS_COLORS = {
    "FEDER": "#2a78d6",  # bleu
    "FSE+": "#eb6834",  # orange
    "FTJ": "#1baf7a",  # aqua
}
