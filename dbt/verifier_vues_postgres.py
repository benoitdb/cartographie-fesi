"""Recoupe les marts dbt contre les 19 vues SQL de `metabase/init/`.

LE FILET DE LA PÉRIODE DE RECOUVREMENT (issue #135, point 3). Depuis #231
(ADR 002), Metabase lit les marts dbt du schéma `marts` ; les vues restent en
place, inutilisées, jusqu'à leur retrait (PR 2 de #231). Ce script vérifie que
les deux disent la même chose, et disparaîtra avec les vues. Les vues `v_by_*`
et `v_pilotage` sont comparées sur 2021-2027 seulement : les marts
correspondants ne couvrent que cette période (#231, option A).

Complémentaire de `verifier_equivalence.py`, qui compare aux agrégats PYTHON sur
DuckDB, sans infrastructure. Celui-ci compare aux vues SQL sur PostgreSQL, et ne
peut donc pas tourner en CI — c'est le même partage que côté Metabase entre
`verify_aggregates.py` et la suite pytest.

C'est ce recoupement-là qui a attrapé la seule vraie erreur du chantier : un
plafond de cofinancement ultrapériphérique oublié, qui classait 28 opérations de
Martinique en dépassement sans lever la moindre exception.

Prérequis : la stack Metabase tourne (`cd metabase && docker compose up -d`),
`load_data.py` a été rejoué, et `dbt build --target postgres` aussi.

Usage : dbt/venv/bin/python verifier_vues_postgres.py
"""

import os
import sys

import psycopg2

DSN = dict(
    host="localhost",
    port=5437,
    dbname=os.environ.get("POSTGRES_DB", "fesi"),
    user=os.environ.get("POSTGRES_USER", "fesi"),
    password=os.environ.get("POSTGRES_PASSWORD", "fesi_local"),
)

SCHEMA_DBT = os.environ.get("DBT_SCHEMA", "marts")

# (mart dbt, vue SQL, colonnes comparées, filtre éventuel sur la vue).
#
# Les colonnes sont choisies pour comparer ce qui PORTE DU SENS, pas tout : les
# moyennes se déduisent des sommes et des comptages, et les inclure ne ferait
# qu'ajouter du bruit de virgule flottante à un contrôle qui doit être exact.
#
# Les vues de 2021-2027 sont filtrées sur leur période : elles portent les deux,
# là où le mart dbt correspondant part d'un staging mono-source.
P2127 = "periode = '2021-2027'"
COMPARAISONS = [
    ("by_region", "v_by_region", "region, n_operations, montant_ue_total", P2127),
    ("national", "v_national", "n_operations, montant_ue_total", P2127),
    ("interregional", "v_interregional", "n_operations, montant_ue_total", P2127),
    ("by_fonds", "v_by_fonds", "fonds, n_operations, montant_ue_total", P2127),
    ("by_region_fonds", "v_by_region_fonds", "region, fonds, n_operations, montant_ue_total", P2127),
    (
        "by_objectif_strategique",
        "v_by_objectif_strategique",
        "objectif_strategique, n_operations, montant_ue_total",
        P2127,
    ),
    ("pilotage", "v_pilotage", "perimetre, fonds, programme, engage, taux, reste_a_engager", P2127),
    (
        "cofinancement_2021_2027",
        "v_cofinancement_2021_2027",
        "numero_operation, depasse_plafond, taux_divergent",
        None,
    ),
    (
        "perimetre_2014_2020",
        "v_perimetre_2014_2020",
        "numero_operation, perimetre, fonds, montant_ue",
        None,
    ),
    ("engage_2014_2020", "v_engage_2014_2020", "perimetre, fonds, n_operations, engage", None),
    ("enveloppes_2014_2020", "v_enveloppes_2014_2020", "perimetre, fonds, programme", None),
    (
        "pilotage_2014_2020",
        "v_pilotage_2014_2020",
        "perimetre, fonds, programme, engage, taux, reste_a_engager",
        None,
    ),
    (
        "cofinancement_2014_2020",
        "v_cofinancement_2014_2020",
        "numero_operation, region, fonds, depasse_plafond, taux_divergent",
        None,
    ),
    (
        "cofinancement_2014_2020_summary",
        "v_cofinancement_2014_2020_summary",
        "region, fonds, n_operations, n_depassements, montant_depassements, n_taux_divergents",
        None,
    ),
    ("engage_all", "v_engage_all", "periode, perimetre, fonds, n_operations, engage", None),
    (
        "pilotage_all",
        "v_pilotage_all",
        "periode, perimetre, fonds, programme, engage, taux, reste_a_engager",
        None,
    ),
    (
        "repartition_all",
        "v_repartition_all",
        "periode, perimetre, fonds, niveau1, niveau2, n_operations, engage",
        None,
    ),
    (
        "cofinancement_all",
        "v_cofinancement_all",
        "periode, region, fonds, n_operations, n_depassements, montant_depassements",
        None,
    ),
    # Les trois partitions d'`agregats.py` (mono-région, interrégional, national).
    # La vue a longtemps perdu l'interrégional, 13 opérations et 1,625 M€ (#138) ;
    # depuis sa correction, elle doit égaler le mart comme les autres (#230).
    ("engage_by_perimetre_fonds", "v_engage_by_perimetre_fonds", "perimetre, fonds, engage", P2127),
]


def comparer(cur, mart, vue, colonnes, filtre):
    """Différence symétrique entre les deux relations, sur les colonnes données."""
    ou = f"WHERE {filtre}" if filtre else ""
    cur.execute(
        f"SELECT {colonnes} FROM {SCHEMA_DBT}.{mart} "
        f"EXCEPT SELECT {colonnes} FROM public.{vue} {ou}"
    )
    en_trop = cur.fetchall()
    cur.execute(
        f"SELECT {colonnes} FROM public.{vue} {ou} "
        f"EXCEPT SELECT {colonnes} FROM {SCHEMA_DBT}.{mart}"
    )
    manquantes = cur.fetchall()
    return en_trop, manquantes


def main():
    echecs = []
    with psycopg2.connect(**DSN) as conn, conn.cursor() as cur:
        for mart, vue, colonnes, filtre in COMPARAISONS:
            en_trop, manquantes = comparer(cur, mart, vue, colonnes, filtre)
            if en_trop or manquantes:
                echecs.append((mart, vue, en_trop, manquantes))
                print(f"❌ {mart} vs {vue} : {len(en_trop)} en trop, {len(manquantes)} manquantes")
            else:
                print(f"✅ {mart} vs {vue}")

    print(f"\n{len(COMPARAISONS)} comparaisons.")
    if echecs:
        print(f"❌ {len(echecs)} divergence(s) — les deux implémentations ont dérivé.")
        for mart, vue, en_trop, manquantes in echecs:
            for ligne in (en_trop + manquantes)[:5]:
                print(f"   {mart}/{vue} : {ligne}")
        sys.exit(1)
    print("✅ Les marts dbt et les vues SQL disent la même chose.")


if __name__ == "__main__":
    main()
