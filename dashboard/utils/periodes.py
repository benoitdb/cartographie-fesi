"""Ce qui change d'une période de programmation à l'autre, côté dashboard (issue #83).

Le dashboard a été écrit contre les libellés de colonnes du fichier 2021-2027 :
« Montant UE », « Total des dépenses éligibles », « Fonds » y sont écrits en
clair dans ~140 endroits. Le fichier Synergie 2014-2020 porte les mêmes notions
sous d'autres libellés (« Montant UE programmé »…), et n'en porte pas d'autres
du tout.

Plutôt que de propager la période jusqu'à chacun de ces endroits, on **adapte au
chargement** : `normaliser_operations` renomme les colonnes équivalentes vers le
libellé canonique du dashboard, et `CAPACITES` dit ce que la période **n'a pas**,
pour que la page en retire les blocs correspondants au lieu de les afficher vides.

Deux pièges que ce module ne masque pas, et ne doit pas masquer :

1. **Renommer n'est pas rendre équivalent.** En 2014-2020 le montant est celui
   *programmé* ; en 2021-2027 celui *conventionné*. Ce sont deux stades
   différents du cycle de vie d'une opération. La colonne interne porte le même
   nom pour que le code aval fonctionne, mais le libellé **affiché** reste celui
   de la période (`libelle_montant`), et `MENTION_MONTANTS_PROGRAMMES` doit
   rester visible partout où des montants 2014-2020 sont présentés.
2. **Le périmètre 2014-2020 est incomplet** (issue #68) : quatre autorités de
   gestion n'utilisaient pas SynergieCDM, leurs opérations vivent dans des
   fichiers séparés, non fusionnés à `data_2014-2020.json`. Toute lecture par
   région, et toute comparaison entre régions ou entre périodes, doit porter
   `AVERTISSEMENT_PERIMETRE`.

La table `COLONNES_EQUIVALENTES` duplique une information qui vit déjà dans
`data-pipeline/schema_source.py` — le dashboard n'importe pas le pipeline. C'est
`tests/test_periodes.py` qui garde les deux alignées : un renommage de colonne
dans le schéma sans report ici fait rougir la suite, au lieu de produire une
page vide en silence.
"""

PERIODE_2021_2027 = "2021-2027"
PERIODE_2014_2020 = "2014-2020"

# clé sémantique -> (libellé 2021-2027, libellé 2014-2020). Le libellé 2021-2027
# est le libellé **canonique** du dashboard, celui vers lequel on normalise —
# non parce qu'il serait meilleur, mais parce que c'est celui que le code
# existant lit déjà.
COLONNES_EQUIVALENTES = {
    "libelle_prog": ("Libellé Programme", "Libellé programme"),
    # Aucun code du dashboard ne lit le numéro CCI à ce jour : déclaré quand même,
    # parce qu'une divergence de casse non normalisée ne se manifeste que le jour
    # où quelqu'un l'utilise, et par une colonne vide plutôt que par une erreur.
    "numcci": ("NUMCCI", "NumCCI"),
    "depenses": ("Total des dépenses éligibles", "Total des dépenses éligibles programmées"),
    "montant_ue": ("Montant UE", "Montant UE programmé"),
}

RENOMMAGES = {
    PERIODE_2014_2020: {
        libelle_1420: libelle_2127
        for libelle_2127, libelle_1420 in COLONNES_EQUIVALENTES.values()
        if libelle_1420 != libelle_2127
    },
    PERIODE_2021_2027: {},
}

MONTANT_UE = "Montant UE"
DEPENSES = "Total des dépenses éligibles"
TAUX_COFINANCEMENT = "Taux de cofinancement"

# Le libellé affiché du montant, lui, ne se normalise pas : cf. piège 1 de la
# docstring.
LIBELLES_MONTANT = {
    PERIODE_2021_2027: "Montant UE",
    PERIODE_2014_2020: "Montant UE programmé",
}

# Ce que chaque période permet d'afficher. Une capacité absente retire un bloc de
# la page ; elle ne le remplit pas de zéros ni de « Non spécifié » (cf. #12 : une
# dimension absente de la source ne doit pas ressembler à une dimension mesurée
# et vide).
CAPACITES = {
    PERIODE_2021_2027: {
        # Objectifs stratégiques renseignés -> treemaps, pilotage par OS, couleurs par OS.
        "dimension_thematique": True,
        # Enveloppes programmées de l'Accord de partenariat -> % consommé, reste
        # à engager, trajectoire.
        "montants_programmes": True,
        # Plafonds réglementaires de cofinancement par catégorie de région.
        "plafonds_cofinancement": True,
        # Le fichier couvre l'ensemble des autorités de gestion.
        "perimetre_complet": True,
    },
    PERIODE_2014_2020: {
        # `Domaine d'intervention` vide à 100 % dans le fichier Synergie (#82).
        "dimension_thematique": False,
        # L'Accord de partenariat 2014-2020 est disponible (docs/sources/), mais
        # ses dotations par programme ne sont pas encore transcrites en données
        # comme l'est le Tableau 9B de 2021-2027 (#79).
        "montants_programmes": False,
        # La règle 2014-2020 est connue (1303/2013 art. 120 §3, REACT-EU à 100 %
        # par dérogation), mais pas encore le rattachement région → catégorie de
        # l'époque : NUTS2010 ≠ NUTS2021, et six régions modernes sur treize sont
        # mixtes contre une seule en 2021-2027 (#81).
        "plafonds_cofinancement": False,
        # Quatre autorités de gestion hors Synergie (#68).
        "perimetre_complet": False,
    },
}

MENTION_MONTANTS_PROGRAMMES = (
    "Les montants 2014-2020 sont des montants **programmés** (à l'engagement de "
    "l'opération), là où ceux de 2021-2027 sont **conventionnés**. Les deux ne se "
    "comparent pas terme à terme."
)

AVERTISSEMENT_PERIMETRE = (
    "**Périmètre incomplet.** Ce fichier est l'extraction Synergie : quatre autorités "
    "de gestion n'utilisaient pas SynergieCDM et n'y figurent qu'à la marge — programme "
    "opérationnel national FSE, Nouvelle-Aquitaine, Bretagne, Normandie. Leurs données "
    "sont publiées à part et consultables sur la page « Validation de la source », mais "
    "ne sont pas fusionnées ici (issue #68). Les totaux par région, et toute comparaison "
    "entre régions ou entre périodes, sous-comptent donc ces quatre périmètres."
)

# Pourquoi chaque capacité manque, à afficher à l'utilisateur. La page dérive
# cette liste de `CAPACITES` plutôt que de la réécrire à la main : une capacité
# retirée d'un côté sans l'autre produirait soit un bloc masqué sans explication,
# soit une explication pour un bloc pourtant affiché.
#
# `perimetre_complet` n'y figure pas : son absence n'est pas un bloc manquant
# mais une réserve sur les chiffres affichés, portée en haut de page par
# AVERTISSEMENT_PERIMETRE.
EXPLICATIONS_ABSENCES = {
    "dimension_thematique": (
        "**Objectifs stratégiques et spécifiques** (treemaps, répartition thématique) : la "
        "dimension thématique de cette source est le « Domaine d'intervention », vide à "
        "100 % dans le fichier Synergie (issue #82)."
    ),
    "montants_programmes": (
        "**Pilotage : % consommé, reste à engager, trajectoire** : ils rapprochent l'engagé "
        "des enveloppes programmées. L'Accord de partenariat 2014-2020 est en main et sa "
        "table de dotations par programme identifiée, mais elle n'est pas encore transcrite "
        "en données exploitables (issue #79)."
    ),
    "plafonds_cofinancement": (
        "**Plafonds réglementaires de cofinancement** : la règle de la période est connue "
        "(règlement 1303/2013, art. 120 §3 — 85 / 80 / 60 / 50 % selon la catégorie de "
        "région, et jusqu'à 100 % pour REACT-EU par dérogation). Ce qui manque est le "
        "rattachement de chaque région à sa catégorie **de l'époque** : les catégories "
        "2021-2027 ne sont pas transposables, et six régions actuelles sur treize réunissent "
        "des anciennes régions de catégories différentes (issue #81)."
    ),
}

MENTION_PLAFONDS_ABSENTS = (
    "Les taux ci-dessous sont **descriptifs**, sans comparaison à une borne. Les plafonds "
    "de la période existent bien (règlement 1303/2013, art. 120 §3 : 85 / 80 / 60 / 50 % "
    "selon la catégorie de région, et jusqu'à 100 % pour REACT-EU par dérogation du "
    "règlement 2020/2221, art. 92 ter §12), mais ils s'appliquent à un découpage des "
    "régions qui n'est plus celui d'aujourd'hui — les afficher demanderait de rattacher "
    "chaque région à sa catégorie de l'époque (issue #81)."
)


def capacites(periode):
    """Ce que la période permet d'afficher. Lève sur une période inconnue plutôt
    que de renvoyer un dictionnaire vide : tout serait masqué en silence, et la
    page paraîtrait simplement pauvre au lieu de signaler l'erreur."""
    if periode not in CAPACITES:
        raise KeyError(f"Période inconnue : {periode!r} (connues : {sorted(CAPACITES)})")
    return CAPACITES[periode]


def libelle_montant(periode):
    """Libellé à afficher pour le montant UE, propre à la période."""
    return LIBELLES_MONTANT.get(periode, MONTANT_UE)


def absences_expliquees(periode):
    """Explications des blocs retirés de la page, dans l'ordre de
    `EXPLICATIONS_ABSENCES`, pour les seules capacités que la période n'a pas."""
    capa = capacites(periode)
    return [texte for capacite, texte in EXPLICATIONS_ABSENCES.items() if not capa[capacite]]


def _taux(montant_ue, depenses):
    """Part du financement UE dans les dépenses éligibles, ou None.

    None plutôt que 0 quand les dépenses sont absentes ou nulles : un taux de 0
    se lirait comme une opération financée à 0 % par l'UE, ce qui est une
    information, alors qu'on n'en a aucune. Les fonctions aval (`compute_*`,
    `detect_*`) écartent déjà les valeurs manquantes."""
    if not isinstance(montant_ue, (int, float)) or not isinstance(depenses, (int, float)):
        return None
    if not depenses or depenses != depenses:  # 0, ou NaN
        return None
    return montant_ue / depenses


def normaliser_operations(operations, periode):
    """Opérations aux libellés canoniques du dashboard.

    Deux transformations, et rien d'autre — aucune valeur n'est inventée :

    - les colonnes équivalentes sont **renommées** (`RENOMMAGES`) ;
    - le taux de cofinancement, colonne du fichier 2021-2027 mais **absente** du
      fichier 2014-2020, est **dérivé** des deux montants quand il manque. Il
      s'agit d'un simple quotient de deux colonnes présentes, pas d'une donnée
      reconstituée.

    Les colonnes qui n'ont pas d'équivalent (objectif stratégique, objectif
    spécifique, type d'intervention) ne sont **pas** créées : c'est `CAPACITES`
    qui dit à la page de ne pas les demander.
    """
    renommage = RENOMMAGES.get(periode, {})
    normalisees = []
    for op in operations:
        if renommage:
            op = {renommage.get(cle, cle): valeur for cle, valeur in op.items()}
        else:
            op = dict(op)
        if TAUX_COFINANCEMENT not in op:
            op[TAUX_COFINANCEMENT] = _taux(op.get(MONTANT_UE), op.get(DEPENSES))
        normalisees.append(op)
    return normalisees
