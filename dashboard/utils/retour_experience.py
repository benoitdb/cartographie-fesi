"""Retour d'expérience FEDER 2014-2020 par objectif stratégique 2021-2027.

Source : ANCT, « Synthèse des études — Programmation FEDER 2014-2020 en France
métropolitaine », version janvier 2020 (16 pages). Grilles « facteurs de
dynamique de programmation, écueils à éviter et pistes de réflexion » extraites
par thématique 2014-2020 (OT 1 à 6), puis regroupées par OS 2021-2027.

Le mapping OT 14-20 → OS 21-27 suit la correspondance réglementaire :
  OT 1 (RDI) + OT 2 (Numérique) + OT 3 (PME) → OS 1 « Europe plus intelligente »
  OT 4 (Transition énergétique) + OT 5 (Climat) + OT 6 (Environnement) → OS 2 « Europe plus verte »
Les OS 3, 4, 5 et 8 ne sont pas couverts (étude FEDER uniquement, pas FSE).

Issue #42.
"""

RETOUR_EXPERIENCE_ANCT = {
    "1. Europe plus intelligente": {
        "label_court": "RDI, numérique, aide aux entreprises",
        "ot_source": "OT 1, 2, 3",
        "ecueils": [
            {
                "theme": "Aides d'État",
                "texte": (
                    "Complexité réglementaire récurrente : plans de financement "
                    "bloqués, interprétation trop contraignante, régimes "
                    "FEDER/ADEME parfois différents."
                ),
            },
            {
                "theme": "Maturité des projets",
                "texte": (
                    "Maturité insuffisante des projets déposés au démarrage des "
                    "programmes, en particulier sur le numérique et les usages."
                ),
            },
            {
                "theme": "Dispersion",
                "texte": (
                    "Dispersion en petits projets aux coûts de gestion "
                    "disproportionnés, notamment sur les usages du numérique "
                    "et le soutien aux PME."
                ),
            },
            {
                "theme": "Porteurs récurrents",
                "texte": (
                    "Mobilisation récurrente des mêmes porteurs de projets, "
                    "habitués aux fonds européens, au détriment du "
                    "renouvellement."
                ),
            },
            {
                "theme": "Délais d'instruction",
                "texte": (
                    "Inadéquation du temps d'instruction des demandes de "
                    "subventions au regard du facteur temps des entreprises."
                ),
            },
        ],
        "facteurs_favorisants": [
            "Adossement au Contrat de Plan État-Région (projets publics de RDI)",
            "Appels à projets associés à une animation et un accompagnement des candidats",
            "Instruments financiers (IF) : réactivité et sécurisation des process",
            "Intégration du FEDER dans les stratégies régionales de développement économique",
        ],
    },
    "2. Europe plus verte": {
        "label_court": "Transition énergétique, climat, environnement",
        "ot_source": "OT 4, 5, 6",
        "ecueils": [
            {
                "theme": "Aides d'État et réglementation",
                "texte": (
                    "Complexité réglementaire : aides d'État, droit de "
                    "l'environnement, marchés publics — blocage fréquent "
                    "sur les projets de production d'EnR et les friches urbaines."
                ),
            },
            {
                "theme": "Approches émergentes",
                "texte": (
                    "Maturité insuffisante des projets sur les approches "
                    "émergentes : adaptation au changement climatique, "
                    "érosion côtière, prévention de la sécheresse."
                ),
            },
            {
                "theme": "Petits projets",
                "texte": (
                    "Démultiplication de petits projets (biodiversité, gestion "
                    "des risques) aux coûts de gestion disproportionnés, "
                    "mobilisant l'administration au détriment de l'animation."
                ),
            },
            {
                "theme": "Performance énergétique",
                "texte": (
                    "Objectifs de performance énergétique des PO difficiles à "
                    "respecter pour les bâtiments publics ; complexité "
                    "technique freinant l'émergence de projets."
                ),
            },
            {
                "theme": "Stratégies locales",
                "texte": (
                    "Élaboration tardive des stratégies locales (biodiversité, "
                    "risques inondation) à l'origine du retard d'émergence "
                    "de projets au démarrage."
                ),
            },
        ],
        "facteurs_favorisants": [
            "Logement social : bonne appropriation, effet levier du FEDER, relais par l'USH",
            "Partenariat ADEME-autorités de gestion pour les projets d'EnR (bois-énergie, méthanisation)",
            "Stratégies locales (SCORAN, SDTAN, stratégies urbaines intégrées) structurant les projets",
            "Appels à projets sélectifs avec animation dédiée (ex. smart grids Bretagne)",
        ],
    },
}

SOURCE_ANCT = (
    "Source : ANCT, « Synthèse des études — Programmation FEDER 2014-2020 "
    "en France métropolitaine », version janvier 2020. Constats nationaux, "
    "à contextualiser localement."
)
