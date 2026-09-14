"""Recoupe l'harmonisation SQL (spike #140) contre le Python de region_mapping.py.

Le modèle `int_harmonize_spike` calcule l'harmonisation en SQL pour les 6 sources
et conserve les colonnes Python (lues du Parquet) à côté. Ce script lit le résultat
et compare opération par opération.

Usage : dbt/venv/bin/python verifier_harmonisation.py
"""

import sys
from pathlib import Path

import duckdb

DBT_DIR = Path(__file__).resolve().parent
BASE = DBT_DIR / "target" / "fesi.duckdb"


def main():
    if not BASE.exists():
        sys.exit(f"Base DuckDB introuvable : {BASE}\nLancer d'abord : dbt build --profiles-dir . --target duckdb")

    con = duckdb.connect(str(BASE), read_only=True)

    total, match_r, match_i, match_n = con.execute("""
    SELECT
        count(*) AS total,
        count(*) FILTER (WHERE sql_regions = python_regions) AS match_regions,
        count(*) FILTER (WHERE sql_interregional = python_interregional) AS match_inter,
        count(*) FILTER (WHERE sql_national = python_national) AS match_national
    FROM int_harmonize_spike
    """).fetchone()

    par_source = con.execute("""
    SELECT
        source_id,
        count(*) AS total,
        count(*) FILTER (WHERE sql_regions = python_regions) AS match_regions,
        count(*) FILTER (WHERE sql_interregional = python_interregional) AS match_inter,
        count(*) FILTER (WHERE sql_national = python_national) AS match_national
    FROM int_harmonize_spike
    GROUP BY source_id
    ORDER BY source_id
    """).fetchall()

    print(f"Harmonisation SQL vs Python — {total} opérations, 6 sources.\n")
    for source_id, n, mr, mi, mn in par_source:
        status = "OK" if mr == n and mi == n and mn == n else "MISMATCH"
        print(f"  {source_id:40s}  {n:6d} ops  regions={mr}/{n}  inter={mi}/{n}  nat={mn}/{n}  [{status}]")

    print(f"\nTotal : regions={match_r}/{total}, interregional={match_i}/{total}, national={match_n}/{total}")

    if match_r == total and match_i == total and match_n == total:
        print("\nÉquivalence confirmée : zéro divergence sur les trois colonnes.")
    else:
        n_mismatch = con.execute("""
        SELECT count(*) FROM int_harmonize_spike
        WHERE sql_regions != python_regions
           OR sql_interregional != python_interregional
           OR sql_national != python_national
        """).fetchone()[0]
        print(f"\nÉCHEC : {n_mismatch} divergence(s).")
        mismatches = con.execute("""
        SELECT source_id, region_source, python_regions, sql_regions,
               python_interregional, sql_interregional,
               python_national, sql_national
        FROM int_harmonize_spike
        WHERE sql_regions != python_regions
           OR sql_interregional != python_interregional
           OR sql_national != python_national
        LIMIT 10
        """).fetchall()
        for m in mismatches:
            print(f"  {m[0]} region={m[1]!r}")
            print(f"    py_reg={m[2]} sql_reg={m[3]}")
            print(f"    inter: py={m[4]} sql={m[5]}, nat: py={m[6]} sql={m[7]}")
        sys.exit(1)

    con.close()


if __name__ == "__main__":
    main()
