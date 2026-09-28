"""Le cycle de la donnée FESI décrit comme un graphe d'assets Dagster (spike #183).

La question du spike : peut-on voir d'un seul tenant, du XLSX jusqu'à
PostgreSQL, ce que l'AGENTS.md décrit aujourd'hui en listes de commandes ?

Règle du spike : **rien n'est réécrit**. Chaque asset appelle le script
existant, dans un sous-process, exactement comme la commande documentée. Dagster
ne porte que l'ordre, la généalogie et la trace des exécutions — si un chiffre
changeait en passant par ici, ce serait un défaut du spike, pas une évolution.

Lancer (port 3001 : 3000 est Metabase, 8501/8502 les deux Streamlit) :

    cd orchestration && venv/bin/dagster dev -m fesi_orchestration.definitions -p 3001
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSpec,
    Definitions,
    MaterializeResult,
    MetadataValue,
    asset,
    define_asset_job,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

RACINE = Path(__file__).resolve().parents[2]
PIPELINE = RACINE / "data-pipeline"
PROCESSED = RACINE / "data" / "processed"
DBT_DIR = RACINE / "dbt"

sys.path.insert(0, str(PIPELINE))
from sources import SOURCES  # noqa: E402

# Toute écriture dans le fichier DuckDB passe par ce pool, limité à 1 dans
# dagster.yaml : DuckDB est mono-écrivain (voir l'artefact « Matérialisé une
# fois, servi deux fois »). Ne protège que des écritures lancées PAR Dagster —
# un client externe qui garde le fichier ouvert le bloque quand même.
POOL_DUCKDB = "duckdb_fesi"


def _nom(fichier_ou_id: str) -> str:
    """Nom d'asset Dagster : [A-Za-z0-9_] seulement."""
    return fichier_ou_id.replace("-", "_").replace(".", "_")


def _lancer(context: AssetExecutionContext, args: list[str], cwd: Path) -> None:
    """Lance un script existant ; sa sortie part dans les logs du run."""
    proc = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True
    )
    if proc.stdout:
        context.log.info(proc.stdout[-4000:])
    if proc.returncode != 0:
        raise RuntimeError(
            f"{' '.join(args)} a échoué (code {proc.returncode}) :\n{proc.stderr[-4000:]}"
        )


# ---------------------------------------------------------------- sources brutes
# Les XLSX ne sont produits par personne ici : ils sont publiés par l'État et
# déposés à la main dans data/raw/. Déclarés comme specs externes pour que la
# généalogie parte bien du fichier, pas du script.

def _cle_xlsx(source_id: str) -> AssetKey:
    return AssetKey(["sources_brutes", _nom(source_id)])


xlsx_sources = [
    AssetSpec(
        _cle_xlsx(source_id),
        group_name="sources_brutes",
        description=f"{conf['label']} — data/raw/{conf['motif_fichier']}",
        metadata={"url_source": MetadataValue.url(conf["url_source"])}
        if conf.get("url_source")
        else {},
    )
    for source_id, conf in SOURCES.items()
]


# -------------------------------------------------------------------- ingestion

def _cle_parquet(source_id: str) -> AssetKey:
    fichier = Path(SOURCES[source_id]["fichier_sortie"]).stem
    return AssetKey(["ingestion", _nom(fichier)])


def _asset_ingestion(source_id: str):
    conf = SOURCES[source_id]
    sortie_json = PROCESSED / conf["fichier_sortie"]
    sortie_parquet = sortie_json.with_suffix(".parquet")

    @asset(
        key=_cle_parquet(source_id),
        deps=[_cle_xlsx(source_id)],
        group_name="ingestion",
        description=(
            f"`python ingest.py {source_id}` → {sortie_parquet.name} "
            f"+ {sortie_json.name} (métadonnées et agrégats)."
        ),
        kinds={"python", "parquet"},
    )
    def _ingestion(context: AssetExecutionContext) -> MaterializeResult:
        _lancer(context, ["ingest.py", source_id], PIPELINE)
        operations = pd.read_parquet(sortie_parquet, columns=[])
        return MaterializeResult(
            metadata={
                "operations": len(operations),
                "parquet_mo": round(sortie_parquet.stat().st_size / 1e6, 2),
                "chemin": MetadataValue.path(str(sortie_parquet)),
            }
        )

    return _ingestion


ingestion = [_asset_ingestion(source_id) for source_id in SOURCES]


# ------------------------------------------------------------------ référentiels
# Ces scripts ne lisent AUCUNE sortie d'ingest.py : ils dérivent de modules
# committés dans data-pipeline/reference/. Le graphe l'a montré (spike #183) :
# seul beneficiaires_fuzzy.py dépend d'ingest.py, et il est déclaré à part plus bas.

REFERENTIELS = {
    "programme_totals": ["programme_totals.json", "programme_detail.json"],
    "dotations_os_totals": ["dotations_os.json"],
    "interreg_totals": ["interreg.json"],
    "transferts_solidarite_totals": ["transferts_solidarite.json"],
    "categories_ue_2014_2020": ["categories_ue_2014_2020.json"],
    "programme_totals_2014_2020": [
        "programme_totals_2014_2020.json",
        "programme_detail_2014_2020.json",
    ],
}


def _asset_referentiel(script: str, sorties: list[str]):
    @asset(
        key=AssetKey(["referentiels", script]),
        group_name="referentiels",
        description=f"`python {script}.py` → {', '.join(sorties)}",
        kinds={"python", "json"},
    )
    def _referentiel(context: AssetExecutionContext) -> MaterializeResult:
        _lancer(context, [f"{script}.py"], PIPELINE)
        return MaterializeResult(metadata={"fichiers": ", ".join(sorties)})

    return _referentiel


referentiels = [_asset_referentiel(s, f) for s, f in REFERENTIELS.items()]

# Committé, produit une fois par an par un appel réseau (Wikidata) : jamais
# relancé par une régénération de routine, donc externe au graphe.
region_metadata = AssetSpec(
    AssetKey(["referentiels", "region_metadata"]),
    group_name="referentiels",
    description="region_metadata.json — Wikidata, one-shot annuel, committé.",
)


# Le seul script qui lit une sortie d'ingest.py (data.parquet, 2021-2027) :
# rapprochements approchés de bénéficiaires entre régions (issue #23). Absent de
# la première version du spike parce que cassé (#184, corrigé par la PR #187).
@asset(
    key=AssetKey(["enrichissement", "beneficiaires_fuzzy"]),
    deps=[_cle_parquet("2021-2027-conventionnees")],
    group_name="ingestion",
    description="`python beneficiaires_fuzzy.py` → beneficiaires_fuzzy.json",
    kinds={"python", "json"},
)
def beneficiaires_fuzzy(context: AssetExecutionContext) -> None:
    _lancer(context, ["beneficiaires_fuzzy.py"], PIPELINE)


# --------------------------------------------------------------------- codegen
# Sources dbt réellement lues : bretagne (non officiel) est ingérée mais n'entre
# pas dans dbt (substituée par bretagne-officiel).
SOURCES_DBT = [s for s in SOURCES if s != "2014-2020-bretagne"]

CLE_CODEGEN = AssetKey(["dbt_codegen"])


@asset(
    key=CLE_CODEGEN,
    # Les Parquet (libellés réels du staging) ET quatre JSON d'où sortent les
    # seeds (generer.py:184-235). Cette seconde moitié n'est écrite nulle part
    # ailleurs que dans le code de generer.py : trouvée en le relisant.
    deps=[_cle_parquet(s) for s in SOURCES_DBT]
    + [
        AssetKey(["referentiels", "programme_totals"]),
        AssetKey(["referentiels", "programme_totals_2014_2020"]),
        AssetKey(["referentiels", "categories_ue_2014_2020"]),
        AssetKey(["referentiels", "region_metadata"]),
    ],
    group_name="transformation",
    description=(
        "`python dbt/generer.py` — staging, seeds et variables de règles générés "
        "depuis le Python. Obligatoire avant tout dbt build (issue #125)."
    ),
    kinds={"python"},
)
def dbt_codegen(context: AssetExecutionContext) -> None:
    _lancer(context, [str(DBT_DIR / "generer.py")], RACINE)


# -------------------------------------------------------------------------- dbt
# `dagster dev` n'active pas le venv, et `prepare_if_dev()` construit SA PROPRE
# ressource dbt, qui cherche `dbt` dans le PATH sans accepter de chemin : sans
# cette ligne, le code se charge en Python mais l'interface affiche un graphe
# vide (constaté pendant le spike — le chargement direct du module ne le voit pas).
BIN_VENV = str(Path(sys.executable).parent)
os.environ["PATH"] = BIN_VENV + os.pathsep + os.environ.get("PATH", "")

projet_dbt = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR, target="duckdb")
projet_dbt.prepare_if_dev()

# Le staging DuckDB lit les Parquet par `read_parquet(...)` et non par
# `source()` : dbt ne connaît donc PAS ce lien, et le manifest le perd. Sans ce
# raccord, la généalogie s'arrête au staging — c'est précisément la coupure que
# le spike devait mesurer. On la recoud ici, explicitement.
STAGING_VERS_SOURCE = {
    f"stg_operations_{_nom(s)}": s for s in SOURCES_DBT
}


class TraducteurFesi(DagsterDbtTranslator):
    def get_asset_spec(self, manifest, unique_id, project):
        spec = super().get_asset_spec(manifest, unique_id, project)
        noeud = manifest["nodes"].get(unique_id) or manifest["sources"].get(unique_id)
        nom = noeud["name"]
        ajouts = []
        if nom in STAGING_VERS_SOURCE:
            ajouts = [_cle_parquet(STAGING_VERS_SOURCE[nom]), CLE_CODEGEN]
        elif noeud["resource_type"] == "seed":
            ajouts = [CLE_CODEGEN]
        if ajouts:
            spec = spec.merge_attributes(deps=ajouts)
        return spec.replace_attributes(group_name="transformation")


@dbt_assets(
    manifest=projet_dbt.manifest_path,
    project=projet_dbt,
    dagster_dbt_translator=TraducteurFesi(),
    pool=POOL_DUCKDB,
)
def modeles_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    # `build` et non `run` : les tests dbt tournent au passage et un test en
    # échec apparaît sur l'asset concerné.
    yield from dbt.cli(["build"], context=context).stream()


# -------------------------------------------------------------------- restitution
# La cible PostgreSQL : `load_data.py`, découplé par choix (ingest.py ne dépend
# d'aucune base). Demande la stack Docker ; hors de la sélection par défaut.

@asset(
    key=AssetKey(["postgres", "operations"]),
    deps=[_cle_parquet(s) for s in SOURCES_DBT]
    + [AssetKey(["referentiels", s]) for s in REFERENTIELS]
    + [region_metadata.key],
    group_name="restitution",
    description=(
        "`python metabase/load_data.py` — charge les sources dans le PostgreSQL de "
        "la stack Metabase (port 5437). Demande `docker compose up -d`."
    ),
    kinds={"python", "postgres"},
)
def postgres_operations(context: AssetExecutionContext) -> None:
    _lancer(context, [str(RACINE / "metabase" / "load_data.py")], RACINE)


# ------------------------------------------------------------------------ jobs
cycle_duckdb = define_asset_job(
    "cycle_duckdb",
    selection=[
        *(a.key for a in ingestion),
        *(a.key for a in referentiels),
        beneficiaires_fuzzy.key,
        CLE_CODEGEN,
        *modeles_dbt.keys,
    ],
    description="XLSX → Parquet → codegen → dbt (DuckDB). Aucune infra requise.",
)

defs = Definitions(
    assets=[
        *xlsx_sources,
        region_metadata,
        *ingestion,
        *referentiels,
        beneficiaires_fuzzy,
        dbt_codegen,
        modeles_dbt,
        postgres_operations,
    ],
    jobs=[cycle_duckdb],
    resources={
        "dbt": DbtCliResource(project_dir=projet_dbt, dbt_executable=f"{BIN_VENV}/dbt")
    },
)
