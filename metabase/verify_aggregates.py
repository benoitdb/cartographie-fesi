"""Tests croisés Python vs SQL (Phase 0, issue #121).

Compare les `aggregates` déjà écrits par `data-pipeline/agregats.py` dans
chaque JSON source aux vues SQL équivalentes (`v_by_region`, `v_national`,
`v_interregional`, `v_by_fonds`, `v_by_region_fonds`, `v_by_objectif_strategique`)
— source par source, jamais blended sur toute une période (cf. commentaire de
`init/02_views.sql`). Ce n'est pas un test pytest : script de vérification
ponctuelle pour la Phase 0, à relancer après tout changement de schéma ou de
vue.
"""

import json
import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 requis : pip install psycopg2-binary")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "processed"
PIPELINE_DIR = SCRIPT_DIR.parent / "data-pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

import sources as sources_module  # noqa: E402

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

RELATIVE_TOLERANCE = 1e-6  # ordre de sommation différent (pandas pairwise vs SQL
# séquentiel) sur le même flottant source : jamais plus qu'un artefact de
# précision (~1e-10 relatif observé), une vraie erreur de données serait
# des ordres de grandeur plus grande que cette marge.


def close_enough(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    return abs(a - b) <= max(0.01, abs(a) * RELATIVE_TOLERANCE)


def check_by_region(cur, source_id, agg_by_region):
    cur.execute(
        "SELECT region, n_operations, montant_ue_total FROM v_by_region WHERE source_id = %s",
        (source_id,),
    )
    sql_rows = {r: (n, m) for r, n, m in cur.fetchall()}
    errors = []
    for region, resume in agg_by_region.items():
        sql = sql_rows.pop(region, None)
        if sql is None:
            errors.append(f"by_region[{region}] absent en SQL")
            continue
        n_sql, montant_sql = sql
        if n_sql != resume["count"] or not close_enough(montant_sql, resume["montant_ue_total"]):
            errors.append(
                f"by_region[{region}] JSON={resume['count']}/{resume['montant_ue_total']:.2f} "
                f"SQL={n_sql}/{float(montant_sql):.2f}"
            )
    for region in sql_rows:
        errors.append(f"by_region[{region}] présent en SQL, absent du JSON")
    return errors


def check_national_interregional(cur, source_id, agg, view, key):
    cur.execute(f"SELECT n_operations, montant_ue_total FROM {view} WHERE source_id = %s", (source_id,))
    row = cur.fetchone()
    errors = []
    if key in agg:
        if row is None:
            errors.append(f"{key} absent en SQL")
        else:
            n_sql, montant_sql = row
            if n_sql != agg[key]["count"] or not close_enough(montant_sql, agg[key]["montant_ue_total"]):
                errors.append(
                    f"{key} JSON={agg[key]['count']}/{agg[key]['montant_ue_total']:.2f} "
                    f"SQL={n_sql}/{float(montant_sql):.2f}"
                )
    elif row is not None:
        errors.append(f"{key} présent en SQL ({row}), absent du JSON")
    return errors


def check_by_fonds(cur, source_id, agg_by_fonds):
    cur.execute(
        "SELECT fonds, n_operations, montant_ue_total FROM v_by_fonds WHERE source_id = %s",
        (source_id,),
    )
    sql_rows = {f: (n, m) for f, n, m in cur.fetchall()}
    errors = []
    for fonds, resume in agg_by_fonds.items():
        sql = sql_rows.pop(fonds, None)
        if sql is None:
            errors.append(f"by_fonds[{fonds}] absent en SQL")
            continue
        n_sql, montant_sql = sql
        if n_sql != resume["count"] or not close_enough(montant_sql, resume["montant_ue_total"]):
            errors.append(
                f"by_fonds[{fonds}] JSON={resume['count']}/{resume['montant_ue_total']:.2f} "
                f"SQL={n_sql}/{float(montant_sql):.2f}"
            )
    for fonds in sql_rows:
        errors.append(f"by_fonds[{fonds}] présent en SQL, absent du JSON")
    return errors


def check_by_region_fonds(cur, source_id, agg_by_region_fonds):
    cur.execute(
        "SELECT region, fonds, n_operations, montant_ue_total FROM v_by_region_fonds WHERE source_id = %s",
        (source_id,),
    )
    sql_rows = {(r, f): (n, m) for r, f, n, m in cur.fetchall()}
    errors = []
    for key, resume in agg_by_region_fonds.items():
        pair = (resume["region"], resume["fonds"])
        sql = sql_rows.pop(pair, None)
        if sql is None:
            errors.append(f"by_region_fonds[{key}] absent en SQL")
            continue
        n_sql, montant_sql = sql
        if n_sql != resume["count"] or not close_enough(montant_sql, resume["montant_ue_total"]):
            errors.append(
                f"by_region_fonds[{key}] JSON={resume['count']}/{resume['montant_ue_total']:.2f} "
                f"SQL={n_sql}/{float(montant_sql):.2f}"
            )
    for pair in sql_rows:
        errors.append(f"by_region_fonds{pair} présent en SQL, absent du JSON")
    return errors


def check_by_objectif_strategique(cur, source_id, agg_by_objectif):
    cur.execute(
        "SELECT objectif_strategique, n_operations, montant_ue_total FROM v_by_objectif_strategique "
        "WHERE source_id = %s",
        (source_id,),
    )
    sql_rows = {o: (n, m) for o, n, m in cur.fetchall()}
    errors = []
    for objectif, resume in agg_by_objectif.items():
        sql = sql_rows.pop(objectif, None)
        if sql is None:
            errors.append(f"by_objectif_strategique[{objectif}] absent en SQL")
            continue
        n_sql, montant_sql = sql
        if n_sql != resume["count"] or not close_enough(montant_sql, resume["montant_ue_total"]):
            errors.append(f"by_objectif_strategique[{objectif}] JSON≠SQL")
    for objectif in sql_rows:
        errors.append(f"by_objectif_strategique[{objectif}] présent en SQL, absent du JSON")
    return errors


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    total_errors = 0
    for source_id, descriptor in sources_module.SOURCES.items():
        fichier_sortie = descriptor.get("fichier_sortie")
        json_path = DATA_DIR / fichier_sortie
        if not json_path.exists():
            print(f"{source_id}: {fichier_sortie} absent, skip")
            continue
        with open(json_path) as f:
            data = json.load(f)
        agg = data.get("aggregates", {})

        errors = []
        errors += check_by_region(cur, source_id, agg.get("by_region", {}))
        errors += check_national_interregional(cur, source_id, agg, "v_national", "national")
        errors += check_national_interregional(cur, source_id, agg, "v_interregional", "interregional")
        errors += check_by_fonds(cur, source_id, agg.get("by_fonds", {}))
        errors += check_by_region_fonds(cur, source_id, agg.get("by_region_fonds", {}))
        errors += check_by_objectif_strategique(cur, source_id, agg.get("by_objectif_strategique", {}))

        status = "OK" if not errors else f"{len(errors)} écart(s)"
        print(f"{source_id}: {status}")
        for e in errors:
            print(f"    - {e}")
        total_errors += len(errors)

    cur.close()
    conn.close()

    print()
    if total_errors:
        print(f"ÉCHEC : {total_errors} écart(s) au total.")
        sys.exit(1)
    print("Tous les agrégats SQL concordent avec les agrégats JSON (agregats.py).")


if __name__ == "__main__":
    main()
