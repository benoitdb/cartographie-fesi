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
        # Dotations de l'Accord de partenariat 14-20 (section 1.6) et maquettes
        # REACT-EU (rapport d'évaluation ANCT 2024) transcrites — issue #93. La
        # capacité est vraie pour la période, mais pas pour tous ses périmètres :
        # voir `pilotage_disponible()`, quatre d'entre eux restent sans pilotage
        # faute d'un engagé comparable à l'enveloppe (#95).
        "montants_programmes": True,
        # Règle de la période (1303/2013 art. 120 §3) et rattachement région →
        # catégorie de l'époque (décision 2014/99, via
        # data/processed/categories_ue_2014_2020.json) désormais tous deux
        # disponibles — issue #81. Deux différences avec 2021-2027 restent
        # portées à l'écran, elles ne disparaissent pas avec la capacité : six
        # régions modernes sur treize sont mixtes (plafond affiché en fourchette,
        # pas en moyenne pondérée faute de dotations — #93), et REACT-EU déroge
        # aux plafonds (2020/2221 art. 92 ter §12, voir FONDS_HORS_PLAFOND).
        "plafonds_cofinancement": True,
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
#
# Une capacité qu'aucune période n'a en défaut n'y figure pas non plus : son
# explication ne pourrait plus s'afficher, et resterait à contredire l'écran au
# premier changement de règle. C'est ce qui est arrivé à `plafonds_cofinancement`
# quand #81 l'a livrée — son texte disait « ce qui manque est le rattachement
# région → catégorie », devenu faux le jour où ce rattachement est arrivé.
EXPLICATIONS_ABSENCES = {
    "dimension_thematique": (
        "**Objectifs stratégiques et spécifiques** (treemaps, répartition thématique) : la "
        "dimension thématique de cette source est le « Domaine d'intervention », vide à "
        "100 % dans le fichier Synergie (issue #82)."
    ),
}

# Réserve permanente sur les plafonds 2014-2020, à afficher partout où ils servent de
# référence. Ce n'est pas une capacité manquante — les plafonds sont bien appliqués depuis
# #81 — mais deux propriétés de la période qui ne disparaîtront pas : le découpage des
# régions n'est plus celui d'aujourd'hui, et REACT-EU a son propre régime.
MENTION_PLAFONDS_PERIODE = (
    "Les plafonds affichés sont ceux de la période (règlement 1303/2013, art. 120 §3 : "
    "85 % en région moins développée, 60 % en transition, 50 % en région plus développée), "
    "rattachés à la catégorie **de l'époque** de chaque région (décision d'exécution "
    "2014/99/UE), et non à celle de 2021-2027 qui n'est pas transposable.\n\n"
    "Trois fonds en sont **exclus**, chacun relevant d'un autre régime : **FEDER REACT-EU** "
    "(jusqu'à 100 % par dérogation, règlement 2020/2221 art. 92 ter §12), **IEJ** (l'art. 120 "
    "§3 relève lui-même le plafond des axes mettant en œuvre l'Initiative pour l'emploi des "
    "jeunes) et **FEAD**, qui n'est pas un Fonds ESI mais un transfert hors enveloppe "
    "structurelle (art. 94), régi par le règlement 223/2014."
)

# Pourquoi un taux au-dessus du plafond n'est pas, en soi, une irrégularité. À afficher avec
# tout décompte de dépassements : le plafond se fixe par axe prioritaire, pas par opération,
# et le fichier ne porte pas l'axe.
MENTION_PLAFOND_PAR_AXE = (
    "Un taux supérieur au plafond de la catégorie ne signale pas une irrégularité : "
    "l'article 120 fixe le plafond **par axe prioritaire**, pas par opération, et le majore "
    "de **dix points** quand un axe est entièrement mis en œuvre par instruments financiers "
    "ou par développement local (§5). Le fichier ne portant pas l'axe prioritaire, l'écart "
    "est un point à expliquer, pas un constat."
)

# --- Pilotage 2014-2020 (issue #93) -------------------------------------------

# D'où viennent les enveloppes rapprochées de l'engagé, à afficher avec tout taux de
# consommation de la période. Deux provenances, et elles ne sont pas de même nature :
# l'Accord est un texte négocié en amont, le rapport d'évaluation un constat de fin de
# période. Les confondre ferait passer une maquette révisée pour une dotation initiale.
MENTION_PROVENANCE_ENVELOPPES = (
    "Les enveloppes proviennent de deux sources distinctes : les **dotations de l'Accord "
    "de partenariat 2014-2020** (version 4 du 16/10/2019, section 1.6, par programme, fonds "
    "et année) pour le FEDER, le FSE et l'IEJ ; et les **maquettes REACT-EU** relevées par "
    "l'évaluation de l'initiative REACT-EU en France (ANCT, 20/12/2024) — l'Accord, antérieur "
    "à REACT-EU, n'en porte aucune trace. Les premières sont des dotations arrêtées en amont, "
    "les secondes des maquettes constatées en fin de période, après décisions modificatives."
)

# Trois particularités de fonds, à porter là où les cards par fonds s'affichent : sans
# elles, un fonds absent du bloc se lit comme un oubli et l'IEJ comme une anomalie.
MENTION_FONDS_HORS_RAPPROCHEMENT = (
    "**Deux fonds engagés n'ont pas d'enveloppe en face** et sont donc absents de ce bloc, "
    "plutôt qu'affichés à zéro : le **FEAD**, qui n'est pas un Fonds ESI mais un transfert "
    "hors enveloppe structurelle (art. 94, règlement 223/2014), absent de l'Accord ; et le "
    "**FEDER-FSE**, qui n'est pas un fonds mais le libellé porté par les opérations du "
    "programme national d'assistance technique Europ'Act.\n\n"
    "L'**IEJ**, lui, est compté pour sa ressource entière : l'Accord n'inscrit sur sa ligne "
    "que l'allocation spécifique (471,5 M€ au national), la contrepartie FSE de montant "
    "équivalent (473,2 M€) étant portée par la ligne FSE. Une opération IEJ consomme les "
    "deux ; l'enveloppe FSE est donc diminuée d'autant, pour ne rien compter deux fois."
)

# Pourquoi un dépassement ne se lit pas ici comme en 2021-2027 : la période est close, et
# ses maquettes ont été révisées en cours de route.
MENTION_DEPASSEMENT_2014_2020 = (
    "Un taux au-delà de 100 % ne signale pas une surconsommation : la programmation est "
    "close et les maquettes ont été révisées en cours de période, quand les dotations "
    "affichées ici sont celles de l'Accord de 2019 pour tout ce qui n'est pas REACT-EU. "
    "Le rapport d'évaluation ANCT relève d'ailleurs 16 programmes sur 25 dont les montants "
    "REACT-EU FEDER certifiés atteignent ou dépassent leur maquette."
)

# Les quatre périmètres où le pilotage reste masqué : leur engagé vient d'une extraction
# Synergie qui ne les couvre pas (#68), quand leur enveloppe, elle, est complète. Le taux
# affiché serait une donnée manquante déguisée en sous-consommation.
#
# « Ensemble national » et « Volet national » en font partie pour la même raison : le
# programme opérationnel national FSE pèse 4,1 Md€ d'engagements absents de Synergie.
#
# Ce masquage est une mesure d'attente, pas une propriété de la période — d'où une
# constante ici plutôt qu'une capacité dans CAPACITES : ce qui manque n'est pas la donnée
# de référence (elle est transcrite) mais un engagé comparable. Reprise suivie en #95.
PERIMETRES_SANS_PILOTAGE = frozenset({"Bretagne", "Normandie", "Nouvelle-Aquitaine"})

MENTION_PILOTAGE_MASQUE = (
    "**Pas de taux de consommation sur ce périmètre.** Son enveloppe programmée est connue, "
    "mais l'engagé qu'on lui opposerait vient de l'extraction Synergie, qui ne couvre pas "
    "les autorités de gestion concernées — programme opérationnel national FSE, "
    "Nouvelle-Aquitaine, Bretagne, Normandie (issue #68). Leurs opérations sont publiées à "
    "part et visibles sur la page « Validation de la source », mais ne sont pas fusionnées "
    "ici : un taux calculé sans elles afficherait une donnée manquante comme une "
    "sous-consommation. La reprise de ce point est suivie en issue #95."
)


# Enveloppe -> fonds qui l'absorbe quand aucune opération du périmètre ne porte son
# libellé. Constaté sur l'extraction Synergie : **seuls les quatre DROM** (Guadeloupe,
# La Réunion, Martinique, Mayotte) étiquettent leurs opérations `FEDER REACT-EU` ; en
# métropole les mêmes opérations sont rangées sous `FEDER`.
#
# La lecture des chiffres ne laisse guère de doute : en métropole le FEDER engagé dépasse
# son enveloppe de 30 à 90 % (Île-de-France 187 %, Hauts-de-France 134 %) et l'excédent
# vaut à peu près la maquette REACT-EU de la région (Occitanie : 204 M€ d'excédent pour
# 199 M€ de maquette) ; dans les DROM il colle à son enveloppe (103 à 120 %) pendant que
# le libellé REACT-EU en porte 100 à 106 %.
#
# Garder les deux enveloppes séparées afficherait donc, en métropole, une carte REACT-EU
# à 0 % — que le rapport d'évaluation ANCT dément (86,5 % de taux de certification moyen)
# — et un FEDER mécaniquement gonflé. La règle appliquée est donc la même que pour le
# REACT-EU FSE, qui n'a de libellé nulle part : **une enveloppe rejoint le fonds qui porte
# ses opérations ; sans libellé pour la porter, elle rejoint son fonds d'origine.**
FUSIONS_ENVELOPPES_SANS_LIBELLE = {"FEDER REACT-EU": "FEDER"}

MENTION_REACT_EU_FONDU = (
    "Sur ce périmètre, les opérations **FEDER REACT-EU** ne portent pas de libellé de fonds "
    "distinct dans l'extraction Synergie — seuls les DROM en ont un. Sa maquette est donc "
    "comptée avec l'enveloppe FEDER, puisque c'est là que se trouvent les opérations "
    "correspondantes. Les distinguer afficherait un REACT-EU à 0 % et un FEDER gonflé "
    "d'autant."
)


def fusionner_enveloppes_sans_libelle(enveloppes, fonds_engages):
    """Regroupe les enveloppes dont aucun libellé de fonds ne porte d'opération ici.

    `enveloppes` : {fonds: montant}. `fonds_engages` : les libellés de fonds réellement
    présents dans les opérations du périmètre. Renvoie (enveloppes, fonds_fusionnés) —
    le second pour pouvoir dire à l'écran ce qui a été regroupé, plutôt que de le faire
    en silence.

    Ne fusionne que si le fonds d'accueil existe côté enveloppes : sinon la maquette
    disparaîtrait dans un fonds qui n'a pas de dotation, au lieu d'être visible.
    """
    resultat = dict(enveloppes)
    fusionnes = []
    for fonds, accueil in FUSIONS_ENVELOPPES_SANS_LIBELLE.items():
        if fonds in resultat and fonds not in fonds_engages and accueil in resultat:
            resultat[accueil] += resultat.pop(fonds)
            fusionnes.append(fonds)
    return resultat, fusionnes


def pilotage_disponible(perimetre, est_national=False):
    """Le pilotage a-t-il un sens sur ce périmètre ?

    `est_national` couvre les deux périmètres agrégés de la page (« Ensemble national » et
    « Volet national »), qui ne sont pas des régions et ne peuvent donc pas être reconnus
    par leur seul nom. Séparer les deux arguments évite d'avoir à réimporter ici les
    libellés de ces périmètres, définis par la page.
    """
    return not est_national and perimetre not in PERIMETRES_SANS_PILOTAGE


MENTION_REGION_MIXTE = (
    "Cette région réunit des anciennes régions de **catégories différentes**. Les "
    "programmes 2014-2020 étaient bâtis par ancienne région, chacun d'une seule catégorie : "
    "le plafond dépend donc de l'ancienne région dont relève l'opération, information que le "
    "fichier ne porte pas. D'où une **fourchette** plutôt qu'un plafond unique — une moyenne "
    "pondérée supposerait les dotations par programme, non transcrites à ce jour (issue #93)."
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
