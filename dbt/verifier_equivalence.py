"""Recoupe les marts dbt contre les agrégats Python d'`agregats.py`.

C'est le livrable de validation du spike (issue #135, étape 4), dans l'esprit
des `metabase/verify_*.py` : un `dbt test` prouverait qu'une colonne n'est pas
nulle, pas que les chiffres sont les MÊMES qu'aujourd'hui. Or c'est la seule
question qui vaille — une couche dbt qui déplacerait un KPI d'un euro sans le
dire serait pire que pas de couche dbt du tout.

DEUX ORACLES, et c'est le premier résultat du spike qu'il a fallu séparer.

  A. `agregats.calculer_agregats` rejoué SUR LE PARQUET — l'implémentation de
     production, sur exactement la même entrée que dbt. C'est le seul test qui
     mesure ce que le spike cherche : la SQL dbt est-elle fidèle à la règle
     Python ? Critère strict : comptages exacts, montants au centime.

  B. le bloc `aggregates` de `data/processed/data.json` — ce que le dashboard
     Streamlit affiche réellement. Informatif seulement : il diffère du Parquet
     d'environ 0,37 € sur 7,88 Md€, et **cet écart préexiste au spike**.
     `ingest.py` calcule les agrégats sur le DataFrame NON arrondi, puis écrit
     un Parquet arrondi à deux décimales (`prepare_for_parquet`). Tout
     consommateur qui ré-agrège depuis le Parquet — Metabase via `load_data.py`
     aujourd'hui, dbt ici — retombe donc quelques centimes à côté des KPI
     Streamlit. Le harnais le mesure et le rapporte, il ne le fait pas échouer :
     ce n'est pas une divergence de règle, et ce n'est pas dbt qui l'introduit.

Le centime plutôt que l'égalité binaire : les montants sont des DOUBLE des deux
côtés, et deux sommes de 16 625 flottants dans un ordre différent ne donnent pas
le même dernier bit. Le centime est la granularité à laquelle un écart signifie
quelque chose pour un euro public.

Usage : dbt/venv/bin/python verifier_equivalence.py
"""

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

DBT_DIR = Path(__file__).resolve().parent
REPO = DBT_DIR.parent
DATA = REPO / "data" / "processed"
BASE = DBT_DIR / "target" / "fesi.duckdb"
sys.path.insert(0, str(REPO / "data-pipeline"))
sys.path.insert(0, str(REPO / "dashboard"))

import schema_source  # noqa: E402
from agregats import calculer_agregats, partitionner  # noqa: E402

from utils.periodes import (  # noqa: E402
    ENSEMBLE_NATIONAL,
    PERIMETRE_FUSION,
    PERIODE_2014_2020,
    REGIONS_SUBSTITUEES_2014_2020,
    SOURCE_PON_FSE_2014_2020,
    VOLET_NATIONAL,
    normaliser_fichiers_hors_synergie,
    normaliser_operations,
    operations_perimetre_2014_2020,
)

# Fichier Parquet de chaque région à fichier propre (#95) : celui que lit la page 2014-2020.
PARQUET_HORS_SYNERGIE = {
    "Normandie": "data_2014-2020_normandie.parquet",
    "Nouvelle-Aquitaine": "data_2014-2020_nouvelle_aquitaine.parquet",
    "Bretagne": "data_2014-2020_bretagne_officiel.parquet",
}

# Seuil d'égalité des montants, en euros.
CENTIME = 0.01

ecarts = []
controles = 0


def comparer(libelle, attendu, obtenu, seuil=CENTIME):
    global controles
    controles += 1
    if attendu is None and obtenu is None:
        return
    if attendu is None or obtenu is None:
        ecarts.append(f"{libelle}: attendu={attendu!r} obtenu={obtenu!r}")
        return
    if abs(float(attendu) - float(obtenu)) > seuil:
        ecarts.append(
            f"{libelle}: attendu={attendu!r} obtenu={obtenu!r} "
            f"(écart {float(obtenu) - float(attendu):+.4f})"
        )


def comparer_resume(prefixe, attendu, ligne):
    """Bloc d'agrégats commun aux six vues de base (count + 4 montants)."""
    comparer(f"{prefixe}.count", attendu["count"], ligne[0], seuil=0)
    comparer(f"{prefixe}.montant_ue_total", attendu["montant_ue_total"], ligne[1])
    comparer(f"{prefixe}.montant_ue_moyen", attendu["montant_ue_moyen"], ligne[2])
    comparer(f"{prefixe}.depenses_total", attendu["depenses_total"], ligne[3])
    comparer(f"{prefixe}.depenses_moyen", attendu["depenses_moyen"], ligne[4])


def lire_operations(fichier):
    """Opérations d'un Parquet, comme les charge le dashboard
    (`utils/data_loader._load_operations_data`, non importable ici : il dépend de
    Streamlit) : `regions_modernes` y revient en tableau numpy, que le routage compare à
    une liste."""
    df = pd.read_parquet(DATA / fichier)
    if "regions_modernes" in df.columns:
        df["regions_modernes"] = df["regions_modernes"].apply(lambda v: list(v) if v is not None else v)
    return df


def verifier_perimetre_2014_2020(con):
    """Le mart `perimetre_2014_2020` contre le routage Python de la page 2014-2020 (#176).

    Les TABLES de règles sont communes (codegen `generer.py`) ; la LOGIQUE de routage
    existe deux fois, `if/elif` en Python et `UNION`/`CASE` en SQL. Deux chemins Python
    sont confrontés au mart : la fusion d'« Ensemble national », et le routage périmètre par
    périmètre que la page applique quand on choisit une région ou le Volet national.

    Écarts assumés, hors contrat :
      - sources NON filtrées par fonds : le mart émet les 26 dossiers normands sans fonds
        renseigné, que la page écarte par son filtre Fonds — c'est un choix d'écran,
        pas une règle de routage ;
      - « Interrégional », périmètre du sélecteur de la page, n'a pas de ligne dans le mart
        (la fusion l'écarte, comme la vue SQL d'origine)."""
    synergie = normaliser_operations(lire_operations("data_2014-2020.parquet"), PERIODE_2014_2020)
    with open(DATA / "programme_detail_2014_2020.json", encoding="utf-8") as f:
        libelles_programmes = json.load(f)["libelles_programmes"]
    assert set(PARQUET_HORS_SYNERGIE) == set(REGIONS_SUBSTITUEES_2014_2020), "table des fichiers régionaux à jour"
    hors_synergie = normaliser_fichiers_hors_synergie(
        {region: {"operations": lire_operations(fichier)} for region, fichier in PARQUET_HORS_SYNERGIE.items()},
        libelles_programmes,
    )
    pon_fse = normaliser_operations(lire_operations("data_2014-2020_pon_fse.parquet"), SOURCE_PON_FSE_2014_2020)

    mart = {
        perimetre: (n, montant)
        for perimetre, n, montant in con.execute(
            "SELECT perimetre, COUNT(*), SUM(montant_ue) FROM perimetre_2014_2020 GROUP BY perimetre"
        ).fetchall()
    }
    fusion = operations_perimetre_2014_2020(ENSEMBLE_NATIONAL, synergie, hors_synergie, pon_fse)
    par_perimetre = fusion.groupby(PERIMETRE_FUSION)["Montant UE"].agg(["size", "sum"])
    comparer("perimetre_2014_2020.perimetres", len(par_perimetre), len(mart), seuil=0)
    for perimetre, (n, montant) in mart.items():
        attendu = par_perimetre.loc[perimetre] if perimetre in par_perimetre.index else None
        comparer(f"perimetre_2014_2020[{perimetre}].fusion.count", None if attendu is None else attendu["size"], n, seuil=0)
        comparer(f"perimetre_2014_2020[{perimetre}].fusion.montant_ue", None if attendu is None else attendu["sum"], montant)

        selection = VOLET_NATIONAL if perimetre == "national" else perimetre
        page = operations_perimetre_2014_2020(selection, synergie, hors_synergie, pon_fse)
        comparer(f"perimetre_2014_2020[{perimetre}].page.count", len(page), n, seuil=0)
        comparer(f"perimetre_2014_2020[{perimetre}].page.montant_ue", page["Montant UE"].sum(), montant)
    nb_operations = f"{sum(n for n, _ in mart.values()):,}".replace(",", " ")
    print(f"   {len(mart)} périmètres, {nb_operations} opérations, chacun contre deux chemins Python")


def main():
    global controles
    if not BASE.exists():
        raise SystemExit(f"{BASE} absent — lancer `dbt build` d'abord.")
    # Oracle A : la règle de production, rejouée sur l'entrée de dbt.
    df = pd.read_parquet(DATA / "data.parquet")
    cols = schema_source.build_cols(df.columns, schema_source.SCHEMAS["2021-2027"])
    agg = calculer_agregats(df, cols, partitionner(df))
    con = duckdb.connect(str(BASE), read_only=True)

    print("1. by_region (partition mono-région)")
    lignes = dict(
        (r[0], r[1:])
        for r in con.execute(
            "SELECT region, n_operations, montant_ue_total, montant_ue_moyen,"
            " depenses_total, depenses_moyen FROM by_region"
        ).fetchall()
    )
    comparer("by_region.nb_regions", len(agg["by_region"]), len(lignes), seuil=0)
    for region, attendu in agg["by_region"].items():
        if region not in lignes:
            ecarts.append(f"by_region: région {region!r} absente du mart")
            continue
        comparer_resume(f"by_region[{region}]", attendu, lignes[region])

    print("2. by_fonds (toutes partitions)")
    lignes = dict(
        (r[0], r[1:])
        for r in con.execute(
            "SELECT fonds, n_operations, montant_ue_total, montant_ue_moyen,"
            " depenses_total, depenses_moyen FROM by_fonds"
        ).fetchall()
    )
    comparer("by_fonds.nb_fonds", len(agg["by_fonds"]), len(lignes), seuil=0)
    for fonds, attendu in agg["by_fonds"].items():
        if fonds not in lignes:
            ecarts.append(f"by_fonds: fonds {fonds!r} absent du mart")
            continue
        comparer_resume(f"by_fonds[{fonds}]", attendu, lignes[fonds])

    print("3. by_objectif_strategique")
    lignes = dict(
        (r[0], r[1:])
        for r in con.execute(
            "SELECT objectif_strategique, n_operations, montant_ue_total, montant_ue_moyen,"
            " depenses_total, depenses_moyen FROM by_objectif_strategique"
        ).fetchall()
    )
    for objectif, attendu in agg["by_objectif_strategique"].items():
        if objectif not in lignes:
            ecarts.append(f"by_objectif_strategique: {objectif!r} absent du mart")
            continue
        comparer_resume(f"by_objectif_strategique[{objectif}]", attendu, lignes[objectif])

    print("4. national et interregional (partitions 2 et 3)")
    for table, cle in (("national", "national"), ("interregional", "interregional")):
        ligne = con.execute(
            f"SELECT n_operations, montant_ue_total, montant_ue_moyen,"
            f" depenses_total, depenses_moyen FROM {table}"
        ).fetchone()
        comparer_resume(cle, agg[cle], ligne)

    print("5. by_region_fonds")
    lignes = dict(
        ((r[0], r[1]), r[2:])
        for r in con.execute(
            "SELECT region, fonds, n_operations, montant_ue_total FROM by_region_fonds"
        ).fetchall()
    )
    comparer("by_region_fonds.nb_couples", len(agg["by_region_fonds"]), len(lignes), seuil=0)
    for attendu in agg["by_region_fonds"].values():
        cle = (attendu["region"], attendu["fonds"])
        if cle not in lignes:
            ecarts.append(f"by_region_fonds: couple {cle} absent du mart")
            continue
        comparer(f"by_region_fonds{cle}.count", attendu["count"], lignes[cle][0], seuil=0)
        comparer(
            f"by_region_fonds{cle}.montant", attendu["montant_ue_total"], lignes[cle][1]
        )

    print("6. complétude : somme des trois partitions == by_fonds")
    total_partitions = con.execute(
        "SELECT SUM(engage) FROM engage_by_perimetre_fonds"
    ).fetchone()[0]
    total_by_fonds = con.execute("SELECT SUM(montant_ue_total) FROM by_fonds").fetchone()[0]
    comparer("completude.somme_perimetres_vs_by_fonds", total_by_fonds, total_partitions)

    print("7. pilotage : reste_a_engager planché PAR FONDS (#62)")
    # Contrôle de règle, pas de valeur : la somme des restes par fonds doit être
    # >= au reste calculé sur les totaux dès qu'un fonds est en dépassement.
    par_fonds, sur_totaux = con.execute(
        "SELECT SUM(reste_a_engager), GREATEST(SUM(programme) - SUM(engage), 0) FROM pilotage"
    ).fetchone()
    controles += 1
    if float(par_fonds) < float(sur_totaux) - CENTIME:
        ecarts.append(
            f"pilotage: reste par fonds ({par_fonds}) < reste sur totaux ({sur_totaux}) "
            "— le planchage par fonds ne s'applique pas"
        )
    else:
        print(
            f"   reste par fonds = {float(par_fonds):,.0f} € ; "
            f"sur totaux = {float(sur_totaux):,.0f} € "
            f"(écart {float(par_fonds) - float(sur_totaux):,.0f} € absorbé par les dépassements)"
        )

    print("8. oracle B (informatif) : Parquet vs agrégats publiés dans data.json")
    with open(DATA / "data.json", encoding="utf-8") as f:
        agg_publies = json.load(f)["aggregates"]
    total_parquet = con.execute("SELECT SUM(montant_ue_total) FROM by_fonds").fetchone()[0]
    total_publie = sum(v["montant_ue_total"] for v in agg_publies["by_fonds"].values())
    print(
        f"   dbt/Parquet {float(total_parquet):,.2f} € vs data.json {total_publie:,.2f} € "
        f"→ {float(total_parquet) - total_publie:+.2f} €"
    )
    print(
        "   Écart préexistant au spike : agrégats calculés non arrondis, Parquet arrondi "
        "à 2 décimales (ingest.prepare_for_parquet). Ne fait pas échouer le harnais."
    )

    print("9. perimetre_2014_2020 : routage SQL vs routage Python de la page 2014-2020 (#176)")
    verifier_perimetre_2014_2020(con)

    con.close()

    print(f"\n{controles} contrôles (oracle A, strict).")
    if ecarts:
        print(f"❌ {len(ecarts)} écart(s) :")
        for e in ecarts[:40]:
            print(f"   - {e}")
        if len(ecarts) > 40:
            print(f"   ... et {len(ecarts) - 40} autres")
        sys.exit(1)
    print(
        "✅ Marts dbt identiques à `agregats.calculer_agregats` et au routage 2014-2020 de "
        "`utils/periodes.py` sur la même entrée (comptages exacts, montants au centime)."
    )


if __name__ == "__main__":
    main()
