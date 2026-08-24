"""Un descripteur par **source** de données : le seul endroit qui décrit un fichier.

Une source, c'est un fichier d'opérations publié : où le trouver, quelle feuille
lire, quel schéma de colonnes il suit, à quelle date il a été extrait, et quelle
table programme → région s'applique à sa période. `ingest.py` (qui en fait
`data.json`) et `profil_source.py` (qui en fait un rapport de profilage) lisent
**le même** descripteur : sans cela, les deux se décrivent le même fichier
chacun de son côté et divergent au premier export qui bouge — c'est déjà arrivé
sur le motif de nom de fichier, écrit deux fois (issue #12, étape B).

La clé est la source, pas la période : une même période peut avoir plusieurs
fichiers (2014-2020 a le fichier Synergie national, le fichier *programmées*, et
à terme les fichiers hors-Synergie régionaux — issue #68). Le **schéma**, lui,
est bien indexé par période dans `schema_source.SCHEMAS` : ces fichiers-là
partagent leurs colonnes.

Ajouter une source = ajouter une entrée à `SOURCES`.
"""

from pathlib import Path

from region_mapping import PROGRAMME_TO_REGION, PROGRAMME_TO_REGION_2014_2020
from schema_source import (
    SchemaSourceError,
    build_cols,
    millesime_du_fichier,
    schema_de_periode,
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# Correspondance clé sémantique de `profiler_source` → clé interne du schéma.
# `profiler_source` est pure et ne connaît que des clés sémantiques ; les libellés
# réels, eux, viennent toujours de `build_cols`, jamais d'une copie — c'est ce qui
# fait profiter le profil du garde-fou de schéma d'`ingest.py` (issues #45, #69).
_CLES_PROFIL_2021_2027 = {
    "numero_operation": "numero_op",
    "programme": "libelle_prog",
    "beneficiaire": "nom_benef",
    "fonds": "fonds",
    "region": "region",
    "departement": "departement",
    # 2021-2027 porte des objectifs stratégiques/spécifiques ; 2014-2020 un
    # « Domaine d'intervention ». La clé sémantique est commune, le libellé
    # affiché par la page vient du profil — les deux périodes ne sont pas
    # comparables pour autant (cf. #68).
    "dimension_thematique": "objectif_strat",
    # Il n'y a pas de date de *programmation* dans cette source : la date qui
    # marque l'entrée d'une opération est celle de sa première convention. Le
    # profil expose le libellé réel pour que la page nomme ce qu'elle montre.
    "date_programmation": "date_convention",
    "montant_ue": "montant_ue",
    "depenses": "depenses",
    "pays": "pays",
}

_CLES_PROFIL_2014_2020 = {
    **_CLES_PROFIL_2021_2027,
    "dimension_thematique": "domaine_intervention",
    "date_programmation": "date_programmation",
}

# Champs d'un descripteur :
#   label            — libellé lisible, affiché par la page « Validation de la source »
#   periode          — désigne aussi le schéma dans `schema_source.SCHEMAS`
#   motif_fichier    — glob dans `data/raw/` ; le plus récent par ordre alphabétique
#                      l'emporte (les noms sont datés), jamais un chemin codé en dur
#   url_source       — où retélécharger le fichier, cité dans l'erreur s'il manque
#   feuille          — nom **ou** index. 2021-2027 date le nom de sa feuille à chaque
#                      export (« LISTE OPERATION AU 16 03 2026 ») : seul l'index y est
#                      stable. Synergie a un nom stable, mais sa feuille 0 est une
#                      notice — lire la feuille 0 par défaut y donnerait la notice.
#   date_source      — facultative : date d'extraction déclarée, quand le nom de
#                      fichier ne la porte pas (voir `millesime`)
#   programme_to_region — table de rattachement par libellé de programme
#   cles_profil      — clés sémantiques de `profiler_source` → clés internes du schéma
SOURCES = {
    "2014-2020-synergie": {
        "label": "Synergie national (FEDER/FSE/IEJ/FEAD)",
        "periode": "2014-2020",
        "motif_fichier": "liste_operations_synergie_*.xlsx",
        "url_source": (
            "https://www.europe-en-france.gouv.fr/fr/ressources/"
            "liste-des-operations-2014-2020"
        ),
        "feuille": "Liste opérations synergie 14 20",
        # Le nom de ce fichier ne porte pas de préfixe daté : sans cette
        # déclaration, les données 14-20 arriveraient au dashboard sans millésime
        # et la barre latérale n'afficherait rien (issue #47).
        "date_source": "2023-08-30",  # feuille « Informations » du fichier
        "programme_to_region": PROGRAMME_TO_REGION_2014_2020,
        "cles_profil": _CLES_PROFIL_2014_2020,
    },
    "2021-2027-conventionnees": {
        "label": "Opérations conventionnées (FEDER/FSE+/FTJ)",
        "periode": "2021-2027",
        "motif_fichier": "*_liste_operations_conventionnees_*.xlsx",
        "url_source": (
            "https://www.europe-en-france.gouv.fr/fr/ressources/"
            "liste-operations-feder-fse-ftj-2021-2027"
        ),
        "feuille": 0,
        # `date_source` omise : le nom du fichier porte le millésime de l'export
        # (« 20260316_… »). C'est la source que `ingest.py` transforme en
        # `data.json` : son profil décrit donc la donnée qui alimente réellement
        # le reste du dashboard.
        "programme_to_region": PROGRAMME_TO_REGION,
        "cles_profil": _CLES_PROFIL_2021_2027,
    },
}


def source(source_id):
    """Descripteur d'une source, ou une erreur qui liste celles connues."""
    if source_id not in SOURCES:
        raise SchemaSourceError(
            f"Source inconnue : {source_id!r}. Connues : {list(SOURCES)}"
        )
    return SOURCES[source_id]


def trouver_fichier(conf, repertoire_raw=RAW_DIR):
    """Fichier le plus récent correspondant au motif de la source.

    Les noms sont datés, donc l'ordre alphabétique est l'ordre chronologique.
    Retourner le plus récent plutôt qu'un chemin codé en dur évite de régénérer
    silencieusement les données à partir d'un millésime périmé quand un nouvel
    export est déposé — le fichier 2021-2027 est republié 5 fois par an en
    « annule et remplace » (issue #47).
    """
    fichiers = sorted(repertoire_raw.glob(conf["motif_fichier"]))
    if not fichiers:
        raise SchemaSourceError(
            f"Aucun fichier {conf['motif_fichier']} dans {repertoire_raw}. "
            "Le fichier source n'est pas versionné : le télécharger depuis "
            + conf["url_source"]
        )
    return fichiers[-1]


def cols_internes(conf, colonnes_source):
    """Mapping {clé interne: libellé réel}, vérifié contre le schéma de la période."""
    return build_cols(colonnes_source, schema=schema_de_periode(conf["periode"]))


def cols_profil(conf, colonnes_source):
    """Mapping {clé sémantique de `profiler_source`: libellé réel}.

    Passe par `cols_internes`, donc par le contrôle de schéma : une source
    réordonnée fait échouer la génération du profil au lieu de produire un
    rapport faux sur la page qui sert précisément à attester la donnée.
    """
    internes = cols_internes(conf, colonnes_source)
    return {
        semantique: internes[interne]
        for semantique, interne in conf["cles_profil"].items()
    }


def millesime(conf, chemin):
    """Date de l'export : celle déclarée par la source, sinon le préfixe daté du
    nom de fichier. `None` si ni l'une ni l'autre — le pipeline tourne quand
    même, la fraîcheur ne s'affiche simplement pas."""
    return conf.get("date_source") or millesime_du_fichier(chemin)
