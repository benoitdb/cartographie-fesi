"""
Tout ce qui consiste à ne pas faire aveuglément confiance au fichier source.

Deux garde-fous, pour deux modes d'échec silencieux du pipeline (issues #45 et #47) :

1. `trouver_fichier_source` — le fichier est republié 5 fois par an en
   « annule et remplace », avec un nom daté. Un chemin codé en dur fait
   régénérer les données à partir d'un millésime périmé sans la moindre erreur.
2. `build_cols` — le mapping des colonnes se fait par index (choix assumé : les
   libellés sont moins stables que l'ordre). Mais si l'ordre change quand même,
   rien ne le signale : les montants partent dans la mauvaise colonne et le
   pipeline se termine avec un code de sortie 0.

Dans les deux cas le principe est le même : échouer bruyamment plutôt que
produire des données fausses.
"""

import re
import unicodedata

# Libellés attendus, dans l'ordre du fichier source. L'index reste la clé de
# lecture ; cette liste sert uniquement à vérifier que l'index pointe bien sur la
# colonne qu'on croit.
COLONNES_ATTENDUES = [
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

# Le fichier source mélange les deux apostrophes (U+0027 dans "Région de
# l'opération", U+2019 dans "Code postal de l’opération") : comparer les libellés
# au caractère près ferait échouer la vérification sur une simple normalisation
# typographique de l'export, ce qui n'est pas le problème qu'on cherche à
# détecter. On compare donc sur une forme neutralisée.
_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'"})
_ESPACES_RE = re.compile(r"\s+")

_MOTIF_FICHIER_SOURCE = "*_liste_operations_conventionnees_*.xlsx"


class SchemaSourceError(Exception):
    """Le fichier source ne correspond pas au schéma attendu."""


def normalise_libelle(libelle):
    """Forme comparable d'un libellé de colonne : accents conservés (ils sont
    stables), apostrophes unifiées, espaces normalisés, casse ignorée."""
    texte = unicodedata.normalize("NFC", str(libelle)).translate(_APOSTROPHES)
    return _ESPACES_RE.sub(" ", texte).strip().casefold()


def build_cols(colonnes_source):
    """Vérifie que les colonnes du fichier source sont celles attendues, dans
    l'ordre attendu, puis retourne le mapping {clé interne: libellé réel}.

    Lève SchemaSourceError en décrivant le premier écart rencontré, plutôt que de
    laisser le pipeline produire des agrégats faux.
    """
    colonnes_source = list(colonnes_source)

    if len(colonnes_source) < len(COLONNES_ATTENDUES):
        raise SchemaSourceError(
            f"Le fichier source a {len(colonnes_source)} colonnes, "
            f"{len(COLONNES_ATTENDUES)} au minimum sont attendues. "
            "Le format a probablement changé — vérifier le fichier avant de relancer."
        )

    ecarts = [
        f"  position {index} : attendu {attendu!r}, trouvé {colonnes_source[index]!r}"
        for index, (_, attendu) in enumerate(COLONNES_ATTENDUES)
        if normalise_libelle(colonnes_source[index]) != normalise_libelle(attendu)
    ]
    if ecarts:
        raise SchemaSourceError(
            "Les colonnes du fichier source ne correspondent pas au schéma attendu :\n"
            + "\n".join(ecarts)
            + "\n\nLe mapping se faisant par index, continuer produirait des données "
            "fausses sans erreur. Mettre à jour COLONNES_ATTENDUES (schema_source.py) "
            "après avoir vérifié à quoi correspond réellement chaque colonne."
        )

    return {cle: colonnes_source[index] for index, (cle, _) in enumerate(COLONNES_ATTENDUES)}


def trouver_fichier_source(repertoire_raw):
    """Retourne le fichier source le plus récent de `repertoire_raw`.

    Les noms sont préfixés d'une date (`AAAAMMJJ_liste_operations_...`), donc
    l'ordre alphabétique est l'ordre chronologique. Retourner le plus récent
    plutôt qu'un chemin codé en dur évite de régénérer silencieusement les
    données à partir d'un millésime périmé quand un nouvel export est déposé.
    """
    fichiers = sorted(repertoire_raw.glob(_MOTIF_FICHIER_SOURCE))
    if not fichiers:
        raise SchemaSourceError(
            f"Aucun fichier {_MOTIF_FICHIER_SOURCE} dans {repertoire_raw}. "
            "Le fichier source n'est pas versionné : le télécharger depuis "
            "https://www.europe-en-france.gouv.fr/fr/ressources/"
            "liste-operations-feder-fse-ftj-2021-2027"
        )
    return fichiers[-1]
