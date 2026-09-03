"""Vérifie les vues unifiées par période (issue #129, init/05_vues_unifiees.sql).

Script de vérification ponctuelle, pas un test pytest : il lui faut PostgreSQL,
comme `verify_aggregates.py` et `verify_pilotage_2014_2020.py` (cf. #125).

Ce qu'il verrouille, dans l'ordre d'importance :

1. **Le piège du double-comptage.** `v_pilotage` et `v_engage_by_perimetre_fonds`
   produisent aussi des lignes 2014-2020, en sommant les six sources qui se
   chevauchent — c'est faux pour cette période. Les vues `_all` doivent donc
   scoper leur côté 21-27 par `WHERE periode = '2021-2027'`. Ce script échoue si
   quelqu'un retire ce filtre : les totaux 2014-2020 doubleraient.
2. **La fidélité aux vues de période** : `v_pilotage_all` restreinte à une
   période doit être identique, ligne à ligne, à la vue de cette période.

Usage : metabase/venv/bin/python metabase/verify_vues_unifiees.py
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

env = {}
for _line in (SCRIPT_DIR / ".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        env[_k] = _v

# Import tardif, comme load_data.py : le module reste importable sans base.
try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 requis : metabase/venv/bin/pip install psycopg2-binary")


def connect():
    return psycopg2.connect(
        host="localhost",
        port=5437,
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )


def fetch(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


ecarts = []


def compare(nom, attendu, obtenu):
    if attendu == obtenu:
        print(f"  OK   {nom} ({len(attendu)} lignes)")
        return
    ecarts.append(nom)
    print(f"  ÉCART {nom}")
    manquantes = [r for r in attendu if r not in obtenu]
    en_trop = [r for r in obtenu if r not in attendu]
    for r in manquantes[:5]:
        print(f"         manquante : {r}")
    for r in en_trop[:5]:
        print(f"         en trop   : {r}")


def main():
    with connect() as conn, conn.cursor() as cur:
        print("1. Fidélité aux vues de période")

        # v_pilotage_all / 2021-2027 == v_pilotage restreinte à 2021-2027
        compare(
            "v_pilotage_all[2021-2027] == v_pilotage[2021-2027]",
            fetch(cur, """
                SELECT perimetre, fonds, round(programme::numeric, 2), round(engage::numeric, 2)
                FROM v_pilotage WHERE periode = '2021-2027' ORDER BY 1, 2
            """),
            fetch(cur, """
                SELECT perimetre, fonds, round(programme::numeric, 2), round(engage::numeric, 2)
                FROM v_pilotage_all WHERE periode = '2021-2027' ORDER BY 1, 2
            """),
        )

        # v_pilotage_all / 2014-2020 == v_pilotage_2014_2020 (la vue de fusion,
        # PAS v_pilotage, qui est fausse sur cette période)
        compare(
            "v_pilotage_all[2014-2020] == v_pilotage_2014_2020",
            fetch(cur, """
                SELECT perimetre, fonds, round(programme::numeric, 2), round(engage::numeric, 2)
                FROM v_pilotage_2014_2020 ORDER BY 1, 2
            """),
            fetch(cur, """
                SELECT perimetre, fonds, round(programme::numeric, 2), round(engage::numeric, 2)
                FROM v_pilotage_all WHERE periode = '2014-2020' ORDER BY 1, 2
            """),
        )

        compare(
            "v_engage_all[2014-2020] == v_engage_2014_2020",
            fetch(cur, """
                SELECT perimetre, fonds, n_operations, round(engage::numeric, 2)
                FROM v_engage_2014_2020 ORDER BY 1, 2
            """),
            fetch(cur, """
                SELECT perimetre, fonds, n_operations, round(engage::numeric, 2)
                FROM v_engage_all WHERE periode = '2014-2020' ORDER BY 1, 2
            """),
        )

        print("\n2. Absence de double-comptage 2014-2020")
        # Le total 2014-2020 des vues `_all` ne doit JAMAIS approcher la somme
        # v_pilotage[2014-2020] + v_pilotage_2014_2020 : ce serait le signe que
        # le filtre de période a sauté du côté 21-27 de l'union.
        piege = float(fetch(cur, """
            SELECT COALESCE(SUM(engage), 0) FROM v_pilotage WHERE periode = '2014-2020'
        """)[0][0])
        reel = float(fetch(cur, """
            SELECT COALESCE(SUM(engage), 0) FROM v_pilotage_all WHERE periode = '2014-2020'
        """)[0][0])
        attendu = float(fetch(cur, "SELECT COALESCE(SUM(engage), 0) FROM v_pilotage_2014_2020")[0][0])

        print(f"  v_pilotage[2014-2020]      (source du piège) : {piege / 1e6:>10,.0f} M€")
        print(f"  v_pilotage_2014_2020       (référence)       : {attendu / 1e6:>10,.0f} M€")
        print(f"  v_pilotage_all[2014-2020]  (mesuré)          : {reel / 1e6:>10,.0f} M€")
        if abs(reel - attendu) > 1:
            ecarts.append("v_pilotage_all[2014-2020] ne vaut pas v_pilotage_2014_2020")
            print("  ÉCART : le côté 21-27 de l'union n'est pas scopé par période")
        else:
            print("  OK   pas de double-comptage")

        print("\n3. Complétude 2021-2027 : la somme des périmètres == la source")
        # `v_engage_all` sert de socle aux KPI unifiés (montant, opérations) des
        # dashboards par usage : sans filtre de périmètre, la carte doit rendre
        # le total de la période, exactement ce que lit Streamlit. Or les trois
        # partitions d'`agregats.py` (mono-région, interrégional, national) sont
        # exclusives : en oublier une fait un KPI silencieusement trop bas.
        # Ce contrôle a d'abord rougi (13 opérations interrégionales, 1,625 M€
        # manquantes), d'où la troisième branche de l'union.
        (ops_src, eur_src), = fetch(cur, """
            SELECT SUM(n_operations), round(SUM(montant_ue_total)::numeric, 2)
            FROM v_by_fonds WHERE periode = '2021-2027'
        """)
        (ops_all, eur_all), = fetch(cur, """
            SELECT SUM(n_operations), round(SUM(engage)::numeric, 2)
            FROM v_engage_all WHERE periode = '2021-2027'
        """)
        print(f"  v_by_fonds[2021-2027]  (source)  : {ops_src:>6} op., {float(eur_src) / 1e6:>10,.3f} M€")
        print(f"  v_engage_all[2021-2027] (mesuré) : {ops_all:>6} op., {float(eur_all) / 1e6:>10,.3f} M€")
        if (ops_src, eur_src) != (ops_all, eur_all):
            ecarts.append("v_engage_all[2021-2027] ne couvre pas toute la source")
            print("  ÉCART : une partition manque à l'union (interrégional ? national ?)")
        else:
            print("  OK   somme des périmètres == total de la source")

        print("\n4. Aucune période inattendue")
        for vue in ("v_pilotage_all", "v_engage_all"):
            periodes = [p for (p,) in fetch(cur, f"SELECT DISTINCT periode FROM {vue} ORDER BY 1")]
            if periodes != ["2014-2020", "2021-2027"]:
                ecarts.append(f"{vue} : périodes {periodes}")
                print(f"  ÉCART {vue} : {periodes}")
            else:
                print(f"  OK   {vue} : {periodes}")

    print()
    if ecarts:
        sys.exit(f"ÉCHEC — {len(ecarts)} écart(s) : {', '.join(ecarts)}")
    print("Vues unifiées conformes.")


if __name__ == "__main__":
    main()
