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
3. **La complétude de la répartition thématique** (phase B) : `v_repartition_all`
   regroupée par (période, périmètre, fonds) doit redonner `v_engage_all` ligne
   à ligne. C'est ce qui interdit de « nettoyer » la vue en filtrant les
   opérations sans dimension thématique — elles font 90 % du montant 2014-2020,
   et les écarter rendrait un treemap muet sur l'essentiel de la période.
4. **Le plafond de cofinancement 2021-2027 stocké == celui que Python calcule**
   (`dashboard/utils/cofinancement.plafond_categorie`). La colonne est remplie
   au chargement ; ce contrôle attrape une base rechargée avec une version
   antérieure de la règle, ou une catégorie mixte transcrite à la main.

Usage : metabase/venv/bin/python metabase/verify_vues_unifiees.py
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "processed"
DASHBOARD_DIR = SCRIPT_DIR.parent / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))

# La règle de plafond n'est pas retranscrite ici : elle est importée de
# Streamlit, comme load_data.py le fait pour la remplir (contrôle 8).
from utils.cofinancement import plafond_categorie  # noqa: E402

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

        print("\n3 bis. Complétude 2021-2027 de v_engage_by_perimetre_fonds")
        # MÊME contrôle qu'au point 3, sur la vue dont il manquait (issue #138).
        # `v_engage_all` avait ce garde-fou et `v_engage_by_perimetre_fonds` non,
        # si bien que la correction de la partition interrégionale faite en #129
        # n'a jamais été reportée sur elle : elle est restée 1,625 M€ trop basse
        # pendant tout ce temps, sans que rien ne le dise.
        #
        # Scopé à 2021-2027 comme le point 3, et pour la même raison : cette vue
        # n'est pas scopée par période et produit aussi des lignes 2014-2020, en
        # sommant les six sources qui se chevauchent (cf. l'en-tête de
        # 05_vues_unifiees.sql). Elle est juste sur 2021-2027, fausse sur 14-20 —
        # ce contrôle ne prétend donc rien sur cette période-là.
        (eur_perim,), = fetch(cur, """
            SELECT round(SUM(engage)::numeric, 2)
            FROM v_engage_by_perimetre_fonds WHERE periode = '2021-2027'
        """)
        print(f"  v_by_fonds[2021-2027]                 (source)  : {float(eur_src) / 1e6:>10,.3f} M€")
        print(f"  v_engage_by_perimetre_fonds[2021-2027] (mesuré) : {float(eur_perim) / 1e6:>10,.3f} M€")
        if eur_src != eur_perim:
            ecarts.append("v_engage_by_perimetre_fonds[2021-2027] ne couvre pas toute la source")
            print("  ÉCART : une partition manque (interrégional ? national ?)")
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

        print("\n5. Répartition thématique : la somme des dimensions == l'engagé")
        # `v_repartition_all` détaille `v_engage_all` d'un cran (niveau1/niveau2).
        # Regroupée, elle doit lui être identique : c'est ce qui garantit qu'aucune
        # opération n'a été perdue en route par un filtre sur la dimension
        # thématique — le côté 2014-2020 en porte une sur dix seulement.
        compare(
            "v_repartition_all regroupée == v_engage_all",
            fetch(cur, """
                SELECT periode, perimetre, fonds, n_operations, round(engage::numeric, 2)
                FROM v_engage_all ORDER BY 1, 2, 3
            """),
            fetch(cur, """
                SELECT periode, perimetre, fonds, SUM(n_operations)::bigint, round(SUM(engage)::numeric, 2)
                FROM v_repartition_all GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """),
        )

        print("\n6. Couverture thématique réelle, par période")
        # Mesure, pas verdict : l'asymétrie entre les deux périodes est un fait
        # des sources, pas un défaut à corriger. Ce qui EST un défaut, et ce que
        # ce bloc verrouille, c'est qu'elle disparaisse de la vue — si le côté
        # 2014-2020 n'a plus de ligne 'Non renseigné', c'est que quelqu'un a
        # filtré les 90 % de la période qui n'ont pas de domaine d'intervention.
        for periode, colonne in (("2021-2027", "objectif stratégique"), ("2014-2020", "domaine d'intervention")):
            (n_ren, eur_ren, n_non, eur_non), = fetch(cur, f"""
                SELECT
                    COALESCE(SUM(n_operations) FILTER (WHERE niveau1 <> 'Non renseigné'), 0),
                    COALESCE(SUM(engage)       FILTER (WHERE niveau1 <> 'Non renseigné'), 0),
                    COALESCE(SUM(n_operations) FILTER (WHERE niveau1 =  'Non renseigné'), 0),
                    COALESCE(SUM(engage)       FILTER (WHERE niveau1 =  'Non renseigné'), 0)
                FROM v_repartition_all WHERE periode = '{periode}'
            """)
            total = float(eur_ren) + float(eur_non)
            pct = 100 * float(eur_ren) / total if total else 0
            print(f"  {periode} ({colonne}) : {n_ren} op. renseignées, "
                  f"{float(eur_ren) / 1e6:,.0f} M€ sur {total / 1e6:,.0f} M€ ({pct:.1f} %)")
            if n_non == 0 and n_ren == 0:
                ecarts.append(f"v_repartition_all vide pour {periode}")
                print(f"  ÉCART aucune ligne pour {periode}")
        (n_14,), = fetch(cur, """
            SELECT COUNT(*) FROM v_repartition_all
            WHERE periode = '2014-2020' AND niveau1 = 'Non renseigné'
        """)
        if n_14 == 0:
            ecarts.append("v_repartition_all[2014-2020] n'a plus de ligne 'Non renseigné'")
            print("  ÉCART : les opérations sans domaine d'intervention ont été filtrées "
                  "(90 % du montant de la période)")
        else:
            print(f"  OK   les opérations sans dimension restent comptées ({n_14} lignes)")

        print("\n7. Cofinancement unifié : fidélité aux vues de période")
        compare(
            "v_cofinancement_all[2014-2020] == v_cofinancement_2014_2020_summary",
            fetch(cur, """
                SELECT region, fonds, n_operations, n_depassements, round(montant_depassements::numeric, 2)
                FROM v_cofinancement_2014_2020_summary ORDER BY 1, 2
            """),
            fetch(cur, """
                SELECT region, fonds, n_operations, n_depassements, round(montant_depassements::numeric, 2)
                FROM v_cofinancement_all WHERE periode = '2014-2020' ORDER BY 1, 2
            """),
        )
        compare(
            "v_cofinancement_all[2021-2027] == v_cofinancement_2021_2027 agrégée",
            fetch(cur, """
                SELECT region, fonds, COUNT(*)::bigint,
                       COUNT(*) FILTER (WHERE depasse_plafond)::bigint,
                       round(COALESCE(SUM(montant_ue) FILTER (WHERE depasse_plafond), 0)::numeric, 2)
                FROM v_cofinancement_2021_2027 GROUP BY 1, 2 ORDER BY 1, 2
            """),
            fetch(cur, """
                SELECT region, fonds, n_operations, n_depassements, round(montant_depassements::numeric, 2)
                FROM v_cofinancement_all WHERE periode = '2021-2027' ORDER BY 1, 2
            """),
        )

        print("\n8. Plafond 2021-2027 : SQL == Python")
        # Même principe que verify_aggregates.py : la base ne fait pas foi
        # contre la règle Python, elle doit lui être conforme. Le cas qui
        # compte est la catégorie mixte (Auvergne-Rhône-Alpes), dont le plafond
        # est une moyenne pondérée extraite du libellé.
        n_regions, n_plafonds = 0, 0
        for region, categorie, ultraperipherique, plafond_sql in fetch(cur, """
            SELECT region, categorie_ue, ultraperipherique, plafond_cofinancement
            FROM region_metadata ORDER BY 1
        """):
            n_regions += 1
            attendu = plafond_categorie(categorie, ultraperipherique)
            obtenu = float(plafond_sql) if plafond_sql is not None else None
            if attendu is None and obtenu is None:
                continue
            if attendu is None or obtenu is None or abs(attendu - obtenu) > 1e-9:
                ecarts.append(f"plafond {region}")
                print(f"  ÉCART {region} : SQL {obtenu}, Python {attendu}")
            else:
                n_plafonds += 1
        print(f"  OK   {n_plafonds} plafonds conformes sur {n_regions} régions")

        print("\n9. Allocation RUP : cohérente avec le JSON et avec region_metadata")
        rup_json = json.loads((DATA_DIR / "programme_detail.json").read_text()).get("rup") or {}
        attendu_rup = sorted(
            (perimetre, fonds, round(float(montant), 2))
            for perimetre, fonds_dict in rup_json.items()
            for fonds, montant in fonds_dict.items()
        )
        compare(
            "allocations_rup == programme_detail.json[rup]",
            attendu_rup,
            [(p, f, float(m)) for p, f, m in fetch(cur, """
                SELECT perimetre, fonds, round(montant_ue::numeric, 2)
                FROM allocations_rup WHERE periode = '2021-2027' ORDER BY 1, 2
            """)],
        )
        # Tout périmètre porteur d'une allocation RUP doit être ultrapériphérique
        # — sauf `national`, qui n'est pas une région et porte la part FSE+.
        non_rup = fetch(cur, """
            SELECT DISTINCT a.perimetre
            FROM allocations_rup a
            LEFT JOIN region_metadata r ON r.region = a.perimetre
            WHERE a.perimetre <> 'national' AND COALESCE(r.ultraperipherique, FALSE) IS FALSE
            ORDER BY 1
        """)
        if non_rup:
            ecarts.append(f"allocations_rup : périmètres non-RUP {[p for (p,) in non_rup]}")
            print(f"  ÉCART périmètres non ultrapériphériques : {[p for (p,) in non_rup]}")
        else:
            print("  OK   tous les périmètres dotés sont ultrapériphériques (hors volet national)")

    print()
    if ecarts:
        sys.exit(f"ÉCHEC — {len(ecarts)} écart(s) : {', '.join(ecarts)}")
    print("Vues unifiées conformes.")


if __name__ == "__main__":
    main()
