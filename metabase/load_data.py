"""Load FESI JSON data into PostgreSQL for Metabase testing."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 requis : pip install psycopg2-binary")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "processed"

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

COLUMN_MAP_2021_2027 = {
    "Numéro Opération": "numero_operation",
    "NUMCCI": "numcci",
    "Libellé Programme": "libelle_programme",
    "Intitulé du projet": "intitule_projet",
    "Nom du bénéficiaire": "nom_beneficiaire",
    "Code postal du bénéficiaire": "cp_beneficiaire",
    "Code postal de l'opération": "cp_operation",
    "Zone": "zone",
    "Département de l'opération": "departement",
    "Région de l'opération": "region_source",
    "Pays": "pays",
    "Fonds": "fonds",
    "Objectif stratégique": "objectif_strategique",
    "Objectif spécifique": "objectif_specifique",
    "Objectif spécifique (Code et libellé)": "objectif_specifique_code",
    "Type d'intervention": "type_intervention",
    "Total des dépenses éligibles": "depenses_eligibles",
    "Taux de cofinancement": "taux_cofinancement",
    "Montant UE": "montant_ue",
    "Date première convention": "date_premiere_convention",
    "Date de début de l'opération": "date_debut",
    "Date de fin de l'opération": "date_fin",
    "is_interregional": "is_interregional",
    "is_national": "is_national",
}


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


def load_operations(cur, json_path, periode):
    with open(json_path) as f:
        data = json.load(f)

    ops = data["operations"]
    print(f"  {json_path.name}: {len(ops)} opérations")

    date_cols = {"date_premiere_convention", "date_debut", "date_fin"}
    numeric_cols = {"depenses_eligibles", "taux_cofinancement", "montant_ue"}
    bool_cols = {"is_interregional", "is_national"}

    columns = list(COLUMN_MAP_2021_2027.values()) + ["region", "periode"]
    placeholders = ", ".join(["%s"] * len(columns))
    insert = f"INSERT INTO operations ({', '.join(columns)}) VALUES ({placeholders})"

    rows = []
    for op in ops:
        vals = []
        for src_key, db_col in COLUMN_MAP_2021_2027.items():
            raw = op.get(src_key)
            if db_col in date_cols:
                vals.append(parse_date(raw))
            elif db_col in numeric_cols:
                vals.append(parse_numeric(raw))
            elif db_col in bool_cols:
                vals.append(bool(raw) if raw is not None else False)
            else:
                vals.append(str(raw) if raw is not None else None)

        regions = op.get("regions_modernes", [])
        if isinstance(regions, list) and regions:
            region = regions[0]
        elif isinstance(regions, str):
            region = regions
        else:
            region = None
        vals.append(region)
        vals.append(periode)
        rows.append(vals)

    cur.executemany(insert, rows)
    return len(rows)


def load_programme_totals(cur):
    path = DATA_DIR / "programme_totals.json"
    if not path.exists():
        print("  programme_totals.json non trouvé, skip")
        return
    with open(path) as f:
        data = json.load(f)

    count = 0
    for region, fonds_dict in data.items():
        for fonds, montant in fonds_dict.items():
            cur.execute(
                "INSERT INTO programme_totals (periode, region, fonds, montant_ue) VALUES (%s, %s, %s, %s)",
                ("2021-2027", region, fonds, montant),
            )
            count += 1
    print(f"  programme_totals: {count} lignes")


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


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("DELETE FROM operations")
    cur.execute("DELETE FROM programme_totals")

    print("Chargement 2021-2027...")
    data_file = DATA_DIR / "data.json"
    if data_file.exists():
        n = load_operations(cur, data_file, "2021-2027")
        print(f"  → {n} lignes insérées")

    print("Chargement programme_totals...")
    load_programme_totals(cur)

    print("Chargement region_metadata...")
    load_region_metadata(cur)

    cur.execute("SELECT COUNT(*) FROM operations")
    print(f"\nTotal operations en base : {cur.fetchone()[0]}")
    cur.execute("SELECT region, COUNT(*), SUM(montant_ue) FROM operations WHERE region IS NOT NULL GROUP BY region ORDER BY SUM(montant_ue) DESC LIMIT 5")
    print("Top 5 régions :")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} ops, {row[2]:,.0f} € UE")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
