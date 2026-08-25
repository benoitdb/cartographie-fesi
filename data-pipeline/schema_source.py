"""
Tout ce qui consiste à ne pas faire aveuglément confiance au fichier source.

Deux garde-fous, pour deux modes d'échec silencieux du pipeline (issues #45 et #47) :

1. `millesime_du_fichier` — le fichier 2021-2027 est republié 5 fois par an en
   « annule et remplace », avec un nom daté. Sans cette date propagée jusqu'à
   l'écran, rien ne distingue des chiffres du jour d'un millésime périmé. (Le
   choix du fichier lui-même appartient au descripteur de source, `sources.py`.)
2. `build_cols` — le mapping des colonnes se fait par index (choix assumé : les
   libellés sont moins stables que l'ordre). Mais si l'ordre change quand même,
   rien ne le signale : les montants partent dans la mauvaise colonne et le
   pipeline se termine avec un code de sortie 0.

Dans les deux cas le principe est le même : échouer bruyamment plutôt que
produire des données fausses.

Le schéma dépend de la **période** : 2014-2020 et 2021-2027 n'ont ni les mêmes
colonnes, ni le même ordre (issue #12). D'où `SCHEMAS`, indexé par période, et
non une liste unique — les deux fichiers ont 19 et 23 colonnes, et vérifier l'un
contre le schéma de l'autre échouerait dès la position 1.
"""

import re
import unicodedata

# Libellés attendus, dans l'ordre du fichier source. L'index reste la clé de
# lecture ; ces listes servent uniquement à vérifier que l'index pointe bien sur
# la colonne qu'on croit. Les clés internes sont communes aux périodes quand la
# colonne l'est : c'est ce qui permet à un même code aval de lire les deux.
COLONNES_2021_2027 = [
    ("numero_op", "Numéro Opération"),
    ("numcci", "NUMCCI"),
    ("libelle_prog", "Libellé Programme"),
    ("intitule_proj", "Intitulé du projet"),
    ("objectifs_desc", "Objectifs et réalisations escomptés et effectifs"),
    ("nom_benef", "Nom du bénéficiaire"),
    ("cp_beneficiaire", "Code postal du bénéficiaire"),
    ("date_debut", "Date de début de l'opération"),
    ("date_fin", "Date de fin de l'opération"),
    ("cp_operation", "Code postal de l'opération"),
    ("zone", "Zone"),
    ("departement", "Département de l'opération"),
    ("region", "Région de l'opération"),
    ("pays", "Pays"),
    ("type_intervention", "Type d'intervention"),
    ("fonds", "Fonds"),
    ("objectif_spec", "Objectif spécifique"),
    ("objectif_spec_lib", "Objectif spécifique (Code et libellé)"),
    ("objectif_strat", "Objectif stratégique"),
    ("depenses", "Total des dépenses éligibles"),
    ("taux_cofinance", "Taux de cofinancement"),
    ("montant_ue", "Montant UE"),
    ("date_convention", "Date première convention"),
]

# Fichier Synergie 2014-2020 (`liste_operations_synergie_1420_08_2023.xlsx`,
# feuille 2 — la feuille 0 est une notice). Mêmes clés internes que ci-dessus
# quand la colonne existe dans les deux périodes ; l'ordre, lui, diffère.
#
# Trois colonnes de 2021-2027 n'existent pas ici : `objectif_strat`,
# `objectif_spec` (la dimension thématique 14-20 est le `Domaine d'intervention`,
# vide à 100 % dans ce fichier), `taux_cofinance` et `date_convention` (la date
# de référence est celle de la **programmation**). Trois colonnes sont en plus :
# `resume_op`, `domaine_intervention`, `date_programmation`. Le code aval doit
# donc tester la présence d'une clé, jamais la supposer.
COLONNES_2014_2020 = [
    ("numero_op", "Numéro Opération"),
    ("numcci", "NumCCI"),
    ("libelle_prog", "Libellé programme"),
    ("intitule_proj", "Intitulé du projet"),
    ("resume_op", "Résumé de l'opération"),
    ("nom_benef", "Nom du bénéficiaire"),
    ("cp_beneficiaire", "Code postal du bénéficiaire"),
    ("date_debut", "Date de début de l'opération"),
    ("date_fin", "Date de fin de l'opération"),
    ("cp_operation", "Code postal de l’opération"),
    ("zone", "Zone"),
    ("departement", "Département de l’opération"),
    ("region", "Région de l'opération"),
    ("pays", "Pays"),
    ("domaine_intervention", "Domaine d’intervention"),
    ("date_programmation", "Date de programmation"),
    ("fonds", "Fonds"),
    ("depenses", "Total des dépenses éligibles programmées"),
    ("montant_ue", "Montant UE programmé"),
]

# Fichier PON FSE hors-Synergie (issue #68) : programme opérationnel national
# FSE, publié par fse.gouv.fr, sans rapport de colonnes avec le fichier Synergie
# de la même période — aucune colonne commune au même index. « Fonds » n'existe
# pas dans le fichier : dérivée de `Libellé_po` par le `pretraitement` du
# descripteur de source (`sources.py`), append en dernière colonne avant
# validation du schéma. Plusieurs colonnes de COLONNES_2014_2020 sont absentes
# ici (codes postaux, département, pays, numéro CCI, domaine d'intervention) :
# le code aval doit tester la présence d'une clé, jamais la supposer — déjà vrai
# pour objectif_strat entre 2014-2020 et 2021-2027.
COLONNES_PON_FSE_2014_2020 = [
    ("numero_op", "num_dossier"),
    ("libelle_prog", "Libellé_po"),
    ("axe", "AXE"),
    ("ot", "OT"),
    ("pi", "PI"),
    ("os", "OS"),
    ("region", "Region_adm"),
    ("service_gestionnaire", "Service_gest"),
    ("intitule_proj", "Lib_opé"),
    ("nom_benef", "Lib_org"),
    ("nb_participants", "Nombre de participants prévisionnels"),
    ("depenses", "Dépenses totales"),
    ("montant_ue", "Mont_UE"),
    ("date_debut", "Date début réalisation"),
    ("date_fin", "Date fin réalisation"),
    ("fonds", "Fonds"),  # Dérivée, voir docstring ci-dessus.
]

# Indexé par un identifiant de schéma, pas par période au sens strict : une
# période peut avoir plusieurs fichiers aux colonnes différentes (2014-2020 en a
# au moins deux depuis l'issue #68). Le descripteur de source (`sources.py`)
# désigne le sien via son champ `schema` (par défaut sa `periode`, quand les deux
# coïncident).
# Fichier Nouvelle-Aquitaine hors-Synergie (issue #68) : liste régionale publiée
# par europe-en-nouvelle-aquitaine.eu, l'autorité de gestion n'utilisant pas
# SynergieCDM pour l'essentiel de ses opérations (25 seulement y apparaissent,
# à la marge — voir CLAUDE.md). Colonnes bilingues anglais/français, ce fichier
# n'a ni numéro CCI, ni code postal, ni département, ni objectif stratégique.
# Deux colonnes portent la même valeur (le code du programme de rattachement,
# une des trois anciennes régions pré-2016) : `libelle_prog` et `territoire`
# — aucune n'est une vraie « Région » au sens des autres schémas, dérivée par
# le `pretraitement` du descripteur de source (`sources.py`) puisque le fichier
# ne couvre que la Nouvelle-Aquitaine par construction.
COLONNES_NOUVELLE_AQUITAINE_2014_2020 = [
    ("libelle_prog", "Colonne à masquer lors de la diffusion"),
    ("numero_op", "Operation number"),
    ("nom_benef", "Beneficiary name"),
    ("intitule_proj", "Operation name"),
    ("resume_op", "Operation summary"),
    ("fonds", "Funds"),
    ("date_debut", "Operation start date"),
    ("date_fin", "Operation end date"),
    ("depenses", "Total amount programmed"),
    ("montant_ue", "Amount co-financing European Union"),
    ("taux_cofinance", "Union co-financing rate (%)"),
    ("localisation", "Project location"),
    ("territoire", "Project territory"),
    ("pays", "Country"),
    ("domaine_intervention", "Name of category of intervention for the operation"),
    ("date_maj", "Date of last update"),
    ("region", "Région"),  # Dérivée, voir docstring ci-dessus.
]

# Fichier Bretagne hors-Synergie (issue #68) : liste régionale publiée par
# europe.bzh, l'autorité de gestion n'utilisant pas SynergieCDM. Deux feuilles
# séparées (FEDER, FSE) au même schéma — lues et concaténées par
# `sources.lire_dataframe` (champ `feuilles`), qui pose `Fonds` à une valeur
# constante par feuille avant de les recoller (aucune colonne `Fonds` dans le
# fichier lui-même). Ni numéro d'opération, ni montant UE direct : seul le
# taux de cofinancement l'est, le montant UE se calcule (dépenses × taux) dans
# le `pretraitement` du descripteur — pas ici, ce module ne fait que décrire
# des colonnes qui existent réellement dans le fichier ou que le
# pretraitement pose avant la vérification de schéma.
COLONNES_BRETAGNE_2014_2020 = [
    ("nom_benef", "Nom du bénéficiaire"),
    ("intitule_proj", "Nom de l'opération"),
    ("resume_op", "Résumé de l'opération"),
    ("date_debut", "Date de début de l'opération"),
    ("date_fin", "Date de fin de l'opération"),
    ("date_crpe", "Date de CRPE"),
    ("depenses", "Total des dépenses éligibles"),
    ("taux_cofinance", "Taux de cofinancement UE"),
    ("localisation", "Lieu"),
    ("pays", "Pays"),
    ("categorie_intervention_ref", "Réf. Catégorie d'intervention"),
    ("domaine_intervention", "Catégorie d'intervention dont relève l'opération"),
    ("date_maj", "date de dernière mise à jour"),
    ("fonds", "Fonds"),  # Posée par feuille, voir docstring ci-dessus.
    ("libelle_prog", "Libellé programme"),  # Dérivée, voir sources.py.
    ("region", "Région"),  # Constante, voir sources.py.
    ("montant_ue", "Montant UE"),  # Calculée, voir sources.py.
]

# Quatrième et dernière source hors-Synergie (issue #68) : liste régionale
# Normandie, publiée par europe-en-normandie.eu (page bloquée au scraping
# automatisé — pare-feu Akamai, fichier fourni manuellement). Deux feuilles au
# même schéma, une par ex-région pré-2016 (« PO BN & REACT » = Basse-Normandie
# + REACT-EU, « PO HN » = Haute-Normandie) — lues et concaténées par
# `sources.lire_dataframe` (champ `feuilles`), sans forcer `Fonds` par feuille
# cette fois : contrairement à Bretagne, ce fichier porte déjà une colonne
# `Fond` renseignée ligne à ligne (FEDER/FEDER REACT-EU/FSE/IEJ mélangés dans
# la même feuille). Seul fichier hors-Synergie des quatre à porter un montant
# UE direct (pas de calcul dépenses × taux à faire, contrairement à Bretagne).
COLONNES_NORMANDIE_2014_2020 = [
    ("territoire", "Programme"),
    ("numero_op", "n° Dossier"),
    ("intitule_proj", "Intitulé du projet - Operation name"),
    ("nom_benef", "Nom du bénéficiaire - Beneficiary name"),
    ("siret", "Code SIRET"),
    ("cp_beneficiaire", "CP / zip code"),
    ("ville_beneficiaire", "Siège / City"),
    ("resume_op", "Contexte, présentation générale de l'opération"),
    ("depenses", "Total des dépenses éligibles - Total eligible costs"),
    ("montant_ue", "Montant UE programmé"),
    ("taux_cofinance", "taux de cofinancement UE - EU co-financing rate"),
    ("date_debut", "date début op. / start"),
    ("date_fin", "date fin d'op. / end"),
    ("domaine_intervention", "Catégorie d'intervention - Intervention field"),
    ("fonds", "Fond"),
    ("region", "Région"),  # Dérivée, constante — voir sources.py.
    ("libelle_prog", "Libellé programme"),  # Dérivée, voir sources.py.
]

SCHEMAS = {
    "2021-2027": COLONNES_2021_2027,
    "2014-2020": COLONNES_2014_2020,
    "2014-2020-pon-fse": COLONNES_PON_FSE_2014_2020,
    "2014-2020-nouvelle-aquitaine": COLONNES_NOUVELLE_AQUITAINE_2014_2020,
    "2014-2020-bretagne": COLONNES_BRETAGNE_2014_2020,
    "2014-2020-normandie": COLONNES_NORMANDIE_2014_2020,
}

# Le fichier source mélange les deux apostrophes (U+0027 dans "Région de
# l'opération", U+2019 dans "Code postal de l’opération") : comparer les libellés
# au caractère près ferait échouer la vérification sur une simple normalisation
# typographique de l'export, ce qui n'est pas le problème qu'on cherche à
# détecter. On compare donc sur une forme neutralisée.
_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'"})
_ESPACES_RE = re.compile(r"\s+")

# Préfixe daté du nom de fichier : « 20260316_liste_operations_... ».
_MILLESIME_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})_")


class SchemaSourceError(Exception):
    """Le fichier source ne correspond pas au schéma attendu."""


def normalise_libelle(libelle):
    """Forme comparable d'un libellé de colonne : accents conservés (ils sont
    stables), apostrophes unifiées, espaces normalisés, casse ignorée."""
    texte = unicodedata.normalize("NFC", str(libelle)).translate(_APOSTROPHES)
    return _ESPACES_RE.sub(" ", texte).strip().casefold()


def schema_de_periode(cle_schema):
    """Schéma attendu pour une clé de schéma (période, ou schéma explicite d'un
    descripteur de source quand plusieurs fichiers d'une période ont des colonnes
    différentes — issue #68), ou une erreur qui liste celles connues."""
    if cle_schema not in SCHEMAS:
        raise SchemaSourceError(
            f"Aucun schéma pour {cle_schema!r}. Connus : {list(SCHEMAS)}"
        )
    return SCHEMAS[cle_schema]


def build_cols(colonnes_source, schema=None):
    """Vérifie que les colonnes du fichier source sont celles attendues, dans
    l'ordre attendu, puis retourne le mapping {clé interne: libellé réel}.

    `schema` est une liste de `(clé interne, libellé attendu)` — par défaut celui
    de 2021-2027, la source historique du pipeline. Passer `SCHEMAS["2014-2020"]`
    pour vérifier le fichier Synergie.

    Lève SchemaSourceError en décrivant le premier écart rencontré, plutôt que de
    laisser le pipeline produire des agrégats faux.
    """
    schema = COLONNES_2021_2027 if schema is None else schema
    colonnes_source = list(colonnes_source)

    if len(colonnes_source) < len(schema):
        raise SchemaSourceError(
            f"Le fichier source a {len(colonnes_source)} colonnes, "
            f"{len(schema)} au minimum sont attendues. "
            "Le format a probablement changé — vérifier le fichier avant de relancer."
        )

    ecarts = [
        f"  position {index} : attendu {attendu!r}, trouvé {colonnes_source[index]!r}"
        for index, (_, attendu) in enumerate(schema)
        if normalise_libelle(colonnes_source[index]) != normalise_libelle(attendu)
    ]
    if ecarts:
        raise SchemaSourceError(
            "Les colonnes du fichier source ne correspondent pas au schéma attendu :\n"
            + "\n".join(ecarts)
            + "\n\nLe mapping se faisant par index, continuer produirait des données "
            "fausses sans erreur. Mettre à jour le schéma de la période concernée "
            "(SCHEMAS, schema_source.py) après avoir vérifié à quoi correspond "
            "réellement chaque colonne."
        )

    return {cle: colonnes_source[index] for index, (cle, _) in enumerate(schema)}


def millesime_du_fichier(chemin):
    """Date de l'export, extraite du préfixe du nom de fichier, au format ISO
    (« 20260316_liste_operations_... » → « 2026-03-16 »).

    Cette date accompagne les données jusqu'au dashboard, qui l'affiche : sans
    elle, rien à l'écran ne distingue des chiffres du jour d'un millésime vieux
    de plusieurs mois, alors que la source est republiée 5 fois par an
    (issue #47).

    Retourne None si le nom ne porte pas ce préfixe — un fichier renommé à la
    main reste exploitable, il perd seulement l'affichage de sa date.
    """
    correspondance = _MILLESIME_RE.match(chemin.name)
    return "-".join(correspondance.groups()) if correspondance else None
