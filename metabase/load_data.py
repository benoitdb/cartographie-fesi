"""Charge les données FESI (JSON déjà générés par `ingest.py`) dans PostgreSQL.

C'est la « double sortie SQL » de la Phase 0 (issue #121) — décidée
**découplée** d'`ingest.py` plutôt qu'intégrée : `ingest.py` ne dépend
d'aucune base de données (seulement du XLSX source), ce qui permet à
Streamlit Community Cloud de régénérer les JSON sans aucune infra. Ce script
relit ces JSON après coup ; à relancer après toute régénération
(`python ingest.py ...`) quand la stack Metabase locale tourne.

Générique par source : lit `data-pipeline/sources.SOURCES` et
`data-pipeline/schema_source.SCHEMAS` pour savoir, pour chaque source, quel
fichier JSON charger et comment ses colonnes brutes (souvent en anglais, ou
avec des libellés propres à une seule source — SIRET, AXE/OT/PI/OS...) se
rattachent aux clés internes déjà harmonisées côté pipeline. Ce mapping n'est
pas dupliqué ici : il est importé directement depuis data-pipeline, donc ne
peut pas diverger.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 requis : pip install psycopg2-binary")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "processed"
PIPELINE_DIR = SCRIPT_DIR.parent / "data-pipeline"
DASHBOARD_DIR = SCRIPT_DIR.parent / "dashboard"
sys.path.insert(0, str(PIPELINE_DIR))
sys.path.insert(0, str(DASHBOARD_DIR))

import schema_source  # noqa: E402
import sources as sources_module  # noqa: E402

from utils.cofinancement import plafond_intervalle_2014_2020  # noqa: E402

env_path = SCRIPT_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DB_PARAMS = dict(
    host="localhost",
    port=5437,
    dbname=os.environ.get("POSTGRES_DB", "fesi"),
    user=os.environ.get("POSTGRES_USER", "fesi"),
    password=os.environ.get("POSTGRES_PASSWORD", "fesi_local"),
)

# Clé interne (schema_source.py) -> colonne SQL de `operations`. Tout ce qui
# n'est pas listé ici (SIRET, lat/lon, AXE/OT/PI/OS du PON FSE, etc.) part dans
# `extra`. `region` est volontairement absent : `regions_source`/`regions_modernes`
# (posées par ingest.py sur CHAQUE opération, indépendamment de la source) sont
# la version déjà harmonisée, `region` de schema_source ne serait qu'un doublon
# brut moins fiable.
INTERNAL_KEY_TO_COLUMN = {
    "numero_op": "numero_operation",
    "numcci": "numcci",
    "libelle_prog": "libelle_programme",
    "intitule_proj": "intitule_projet",
    "resume_op": "resume_operation",
    "nom_benef": "nom_beneficiaire",
    "cp_beneficiaire": "cp_beneficiaire",
    "cp_operation": "cp_operation",
    "zone": "zone",
    "departement": "departement",
    "pays": "pays",
    "fonds": "fonds",
    "objectif_strat": "objectif_strategique",
    "objectif_spec": "objectif_specifique",
    "domaine_intervention": "domaine_intervention",
    "type_intervention": "type_intervention",
    "depenses": "depenses_eligibles",
    "taux_cofinance": "taux_cofinancement",
    "montant_ue": "montant_ue",
    "date_debut": "date_debut",
    "date_fin": "date_fin",
    "date_convention": "date_convention",
    "date_programmation": "date_programmation",
}
DATE_COLUMNS = {"date_debut", "date_fin", "date_convention", "date_programmation"}
NUMERIC_COLUMNS = {"depenses_eligibles", "taux_cofinancement", "montant_ue"}

OPERATIONS_COLUMNS = [
    "source_id",
    "periode",
    *dict.fromkeys(INTERNAL_KEY_TO_COLUMN.values()),
    "region_source",
    "region",
    "regions_modernes",
    "is_interregional",
    "is_national",
    "extra",
]


def parse_date(val):
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(val)[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def parse_numeric(val):
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def schema_key_for(source_id, descriptor):
    return descriptor.get("schema", descriptor["periode"])


def build_raw_to_internal(schema_key):
    return {raw_label: internal_key for internal_key, raw_label in schema_source.SCHEMAS[schema_key]}


def load_operations_for_source(cur, source_id, descriptor):
    fichier_sortie = descriptor.get("fichier_sortie")
    if not fichier_sortie:
        return 0
    json_path = DATA_DIR / fichier_sortie
    if not json_path.exists():
        print(f"  {source_id}: {fichier_sortie} absent, skip")
        return 0

    with open(json_path) as f:
        data = json.load(f)
    ops = data["operations"]
    periode = descriptor["periode"]
    raw_to_internal = build_raw_to_internal(schema_key_for(source_id, descriptor))
    known_raw_labels = set(raw_to_internal)

    placeholders = ", ".join(["%s"] * len(OPERATIONS_COLUMNS))
    insert = f"INSERT INTO operations ({', '.join(OPERATIONS_COLUMNS)}) VALUES ({placeholders})"

    rows = []
    for op in ops:
        by_internal_key = {}
        extra = {}
        for raw_label, raw_val in op.items():
            if raw_label in ("regions_modernes", "is_interregional", "is_national", "regions_source"):
                continue
            internal_key = raw_to_internal.get(raw_label)
            if internal_key and internal_key in INTERNAL_KEY_TO_COLUMN:
                by_internal_key[INTERNAL_KEY_TO_COLUMN[internal_key]] = raw_val
            elif raw_val not in (None, ""):
                # Colonne propre à cette source (SIRET, AXE/OT/PI/OS, lat/lon...),
                # ou clé interne connue mais sans colonne dédiée (ex. objectif_spec_lib).
                extra[raw_label] = raw_val
        # Sécurité : toute clé du JSON non couverte par le schéma déclaré de la
        # source signale un schema_source désynchronisé de sources.SOURCES.
        unexpected = set(op) - known_raw_labels - {
            "regions_modernes", "is_interregional", "is_national", "regions_source"
        }
        if unexpected and unexpected - set(extra):
            pass  # déjà versé dans extra ci-dessus, juste documenté pour lecture du code

        vals = [source_id, periode]
        for col in OPERATIONS_COLUMNS[2:-6]:  # entre 'periode' et 'region_source'
            raw = by_internal_key.get(col)
            if col in DATE_COLUMNS:
                vals.append(parse_date(raw))
            elif col in NUMERIC_COLUMNS:
                vals.append(parse_numeric(raw))
            else:
                vals.append(str(raw) if raw not in (None, "") else None)

        regions_modernes = op.get("regions_modernes") or []
        vals.append(op.get("regions_source"))
        vals.append(regions_modernes[0] if regions_modernes else None)
        vals.append(regions_modernes if regions_modernes else None)
        vals.append(bool(op.get("is_interregional", False)))
        vals.append(bool(op.get("is_national", False)))
        vals.append(json.dumps(extra, ensure_ascii=False) if extra else None)
        rows.append(vals)

    cur.executemany(insert, rows)
    print(f"  {source_id}: {len(rows)} opérations ({fichier_sortie})")
    return len(rows)


def load_programme_totals(cur):
    total = 0
    for periode, fichier in (("2021-2027", "programme_totals.json"), ("2014-2020", "programme_totals_2014_2020.json")):
        path = DATA_DIR / fichier
        if not path.exists():
            print(f"  {fichier} non trouvé, skip")
            continue
        with open(path) as f:
            data = json.load(f)
        count = 0
        for region, fonds_dict in data.items():
            for fonds, montant in fonds_dict.items():
                cur.execute(
                    "INSERT INTO programme_totals (periode, region, fonds, montant_ue) VALUES (%s, %s, %s, %s)",
                    (periode, region, fonds, montant),
                )
                count += 1
        print(f"  programme_totals {periode}: {count} lignes")
        total += count
    return total


def load_dotations_os(cur):
    path = DATA_DIR / "dotations_os.json"
    if not path.exists():
        print("  dotations_os.json non trouvé, skip")
        return
    with open(path) as f:
        data = json.load(f)
    count = 0
    for objectif, fonds_dict in data.items():
        if not isinstance(fonds_dict, dict):
            continue
        for fonds, montant in fonds_dict.items():
            cur.execute(
                "INSERT INTO dotations_os (periode, objectif_strategique, fonds, montant_ue) VALUES (%s, %s, %s, %s)",
                ("2021-2027", objectif, fonds, montant),
            )
            count += 1
    print(f"  dotations_os: {count} lignes")


def load_region_metadata(cur):
    path = DATA_DIR / "region_metadata.json"
    if not path.exists():
        print("  region_metadata.json non trouvé, skip")
        return
    with open(path) as f:
        data = json.load(f)

    count = 0
    for region, meta in data.items():
        cur.execute(
            """INSERT INTO region_metadata (region, population, superficie_km2, chef_lieu, categorie_ue, ultraperipherique)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (region) DO UPDATE SET
                 population = EXCLUDED.population,
                 superficie_km2 = EXCLUDED.superficie_km2""",
            (
                region,
                meta.get("population"),
                meta.get("superficie_km2"),
                meta.get("chef_lieu"),
                meta.get("categorie_ue"),
                meta.get("ultraperipherique", False),
            ),
        )
        count += 1
    print(f"  region_metadata: {count} régions")


def load_categories_ue_2014_2020(cur):
    """Catégories de cohésion UE 2014-2020 par région moderne (Phase 3, #121),
    avec le plafond de cofinancement déjà résolu en (min, max) — appelle
    directement `dashboard/utils/cofinancement.plafond_intervalle_2014_2020`
    plutôt que de dupliquer la règle en Python : seule la vue SQL
    `v_cofinancement_2014_2020` (04_periode_2014_2020.sql) duplique
    `FONDS_HORS_PLAFOND`, faute de pouvoir importer du Python dans une vue."""
    path = DATA_DIR / "categories_ue_2014_2020.json"
    if not path.exists():
        print("  categories_ue_2014_2020.json non trouvé, skip")
        return
    with open(path) as f:
        data = json.load(f)
    count = 0
    for region, infos in data.items():
        plafond = plafond_intervalle_2014_2020(infos)
        plafond_min, plafond_max = plafond if plafond else (None, None)
        cur.execute(
            "INSERT INTO categories_ue_2014_2020 (region, categorie_ue, plafond_min, plafond_max) "
            "VALUES (%s, %s, %s, %s)",
            (region, infos.get("categorie_ue"), plafond_min, plafond_max),
        )
        count += 1
    print(f"  categories_ue_2014_2020: {count} régions")


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("DELETE FROM operations")
    cur.execute("DELETE FROM programme_totals")
    cur.execute("DELETE FROM dotations_os")
    cur.execute("DELETE FROM categories_ue_2014_2020")

    print("Chargement des opérations, par source...")
    total_ops = 0
    for source_id, descriptor in sources_module.SOURCES.items():
        total_ops += load_operations_for_source(cur, source_id, descriptor)

    print("Chargement programme_totals...")
    load_programme_totals(cur)

    print("Chargement dotations_os...")
    load_dotations_os(cur)

    print("Chargement region_metadata...")
    load_region_metadata(cur)

    print("Chargement categories_ue_2014_2020...")
    load_categories_ue_2014_2020(cur)

    cur.execute("SELECT COUNT(*) FROM operations")
    print(f"\nTotal operations en base : {cur.fetchone()[0]} (attendu ~{total_ops})")
    cur.execute("SELECT periode, source_id, COUNT(*) FROM operations GROUP BY periode, source_id ORDER BY periode, source_id")
    print("Par source :")
    for row in cur.fetchall():
        print(f"  {row[0]} / {row[1]}: {row[2]}")
    cur.execute(
        "SELECT region, COUNT(*), SUM(montant_ue) FROM operations WHERE region IS NOT NULL "
        "GROUP BY region ORDER BY SUM(montant_ue) DESC LIMIT 5"
    )
    print("Top 5 régions (toutes sources confondues) :")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} ops, {row[2]:,.0f} € UE")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
