"""Génère le modèle de staging et les seeds du spike depuis le Python existant.

POURQUOI UN CODEGEN, ET PAS DU SQL ÉCRIT À LA MAIN — c'est le premier
enseignement du spike (issue #135).

Le renommage « libellé brut du fichier source → clé interne → colonne SQL » a
déjà trois descriptions dans le dépôt (`schema_source.SCHEMAS`,
`periodes.RENOMMAGES`, `load_data.INTERNAL_KEY_TO_COLUMN`). En écrire une
quatrième à la main dans le SQL du staging serait exactement le défaut que dbt
devait corriger. Or dbt ne sait pas importer du Python : ses macros sont du
Jinja, et si `dbt-duckdb` sait exécuter un modèle Python, ce n'est pas au moment
où le SQL est *compilé*. D'où ce script, lancé AVANT `dbt build` : le SQL généré
reste lisible et versionné, la source de vérité reste `schema_source`.

Deux règles Python que le SQL ne peut pas reprendre, et que ce script conserve :

1. `normalise_libelle` (issue #45) — le fichier source mélange les apostrophes
   (U+0027 dans « Région de l'opération », U+2019 dans « Code postal de
   l'opération »). Le garde-fou de schéma compare sur une forme neutralisée ;
   du SQL qui cite les libellés au caractère près ne le peut pas. On apparie
   donc ici les libellés attendus aux libellés RÉELS du Parquet.

2. `cofinancement.plafond_categorie` — le plafond d'Auvergne-Rhône-Alpes est une
   moyenne pondérée extraite d'un libellé (« Mixte : 57% Plus développée / 43%
   En transition ») par expression régulière. Déjà résolu en Python par
   `load_data.py` ; le retranscrire en SQL en ferait une seconde implémentation.

Usage : dbt/venv/bin/python generer.py
"""

import csv
import json
import sys
from pathlib import Path

import pandas as pd

DBT_DIR = Path(__file__).resolve().parent
REPO = DBT_DIR.parent
DATA = REPO / "data" / "processed"
sys.path.insert(0, str(REPO / "data-pipeline"))
sys.path.insert(0, str(REPO / "dashboard"))

import schema_source  # noqa: E402

from utils.cofinancement import plafond_categorie  # noqa: E402

# Même table que `metabase/load_data.INTERNAL_KEY_TO_COLUMN`. Recopiée ici faute
# de pouvoir l'importer : `load_data.py` vit sur la branche `feat/metabase-121`,
# pas sur `main` d'où part ce spike. C'est une duplication ASSUMÉE et
# temporaire — dans une vraie mise en œuvre elle serait importée, comme
# `schema_source` l'est ci-dessus.
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

# CONTRAT DE COLONNES du staging, et troisième coût mesuré par le spike.
#
# Les six sources n'ont PAS les mêmes colonnes : Synergie ignore
# `taux_cofinancement`, le PON FSE ignore les codes postaux et la dimension
# thématique, etc. Côté PostgreSQL ça ne se voit pas — `operations` est une
# table large et `load_data.py` laisse simplement des NULL. Côté dbt, chaque
# staging ne porte que les colonnes de SA source, et le premier UNION ALL entre
# deux sources échoue sur la colonne manquante.
#
# D'où ce contrat : tout modèle de staging expose TOUTES les colonnes internes,
# celles que sa source ne porte pas devenant un NULL typé. C'est ce qui rend les
# `UNION ALL` de la période 2014-2020 possibles — la vue d'origine s'appuyait,
# sans le dire, sur la largeur de la table PostgreSQL.
#
# NUMERIC et DATE plutôt que DOUBLE/TIMESTAMP : les deux dialectes les écrivent
# pareil (`DOUBLE` n'existe pas sous ce nom en PostgreSQL, qui veut
# `DOUBLE PRECISION`).
TYPE_SQL_PAR_COLONNE = {
    "depenses_eligibles": "NUMERIC",
    "taux_cofinancement": "NUMERIC",
    "montant_ue": "NUMERIC",
    "date_debut": "DATE",
    "date_fin": "DATE",
    "date_convention": "DATE",
    "date_programmation": "DATE",
}

# Posées par `ingest.py` sur chaque opération, donc absentes de tout schéma de
# source. `region` = première région moderne, comme `load_data.py`.
# `regions_modernes[1]` : indexation à 1 dans DuckDB comme dans PostgreSQL
# (LIST et TEXT[]) — un des rares endroits où les deux dialectes coïncident.
COLONNES_HARMONISEES = [
    ("regions_source", "region_source"),
    ("regions_modernes[1]", "region"),
    ("regions_modernes", "regions_modernes"),
    ("is_interregional", "is_interregional"),
    ("is_national", "is_national"),
]

ENTETE = """-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma {cle!r}).
-- Voir la docstring de generer.py pour pourquoi ce SQL n'est pas écrit à la main.
--
-- LE POINT DE FORK entre les deux cibles, et le coût le plus net mesuré par le
-- spike (#135) : les deux branches ci-dessous ne partagent RIEN.
--   DuckDB     lit le Parquet et fait le renommage en SQL ;
--   PostgreSQL n'a rien à renommer — `metabase/load_data.py` l'a déjà fait en
--              Python au chargement, et `operations` porte les colonnes internes.
-- Ce n'est pas un défaut de dbt : le projet a aujourd'hui deux frontières
-- d'entrée différentes. Tant que le chargement PostgreSQL passe par du Python
-- qui renomme, dbt ne peut unifier que les marts, jamais cette couche-ci.
"""


def libelles_reels(parquet_path):
    """Libellés réels du Parquet, indexés par leur forme neutralisée."""
    colonnes = pd.read_parquet(parquet_path).columns
    return {schema_source.normalise_libelle(c): c for c in colonnes}


def generer_staging(source_id, cle_schema, periode, parquet, sortie):
    reels = libelles_reels(parquet)
    paires, manquantes = [], []
    for cle_interne, libelle_attendu in schema_source.schema_de_periode(cle_schema):
        colonne_sql = INTERNAL_KEY_TO_COLUMN.get(cle_interne)
        if colonne_sql is None:
            continue  # clé sans colonne dédiée (objectifs_desc, objectif_spec_lib) -> `extra`
        reel = reels.get(schema_source.normalise_libelle(libelle_attendu))
        if reel is None:
            manquantes.append(libelle_attendu)
            continue
        paires.append((f'"{reel}"', colonne_sql))

    if manquantes:
        raise SystemExit(f"{source_id}: colonnes attendues absentes du Parquet : {manquantes}")

    # Contrat de colonnes : compléter par des NULL typés ce que cette source
    # n'a pas (cf. TYPE_SQL_PAR_COLONNE).
    portees = {alias for _, alias in paires}
    for colonne in dict.fromkeys(INTERNAL_KEY_TO_COLUMN.values()):
        if colonne not in portees:
            type_sql = TYPE_SQL_PAR_COLONNE.get(colonne, "VARCHAR")
            paires.append((f"CAST(NULL AS {type_sql})", colonne))

    paires += COLONNES_HARMONISEES

    duckdb = (
        "\n{% if target.type == 'duckdb' %}\n"
        f"SELECT\n    '{source_id}' AS source_id,\n    '{periode}' AS periode,\n"
        + ",\n".join(f"    {expr} AS {alias}" for expr, alias in paires)
        + f"\nFROM read_parquet('{{{{ var(\"chemin_data\") }}}}/{parquet.name}')\n"
    )
    postgres = (
        "{% else %}\n"
        "SELECT\n    source_id,\n    periode,\n"
        + ",\n".join(f"    {alias}" for _, alias in paires)
        + "\nFROM {{ source('fesi', 'operations') }}\n"
        f"WHERE source_id = '{source_id}'\n"
        "{% endif %}\n"
    )

    sortie.write_text(ENTETE.format(cle=cle_schema) + duckdb + postgres, encoding="utf-8")
    print(f"  {sortie.relative_to(DBT_DIR)} ({len(paires)} colonnes, 2 branches de cible)")


def generer_seed_programme_totals(sortie):
    with open(DATA / "programme_totals.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["periode", "region", "fonds", "montant_ue"])
        n = 0
        for region, par_fonds in data.items():
            for fonds, montant in par_fonds.items():
                w.writerow(["2021-2027", region, fonds, montant])
                n += 1
    print(f"  {sortie.relative_to(DBT_DIR)} ({n} lignes)")


def generer_seed_region_metadata(sortie):
    """Plafond résolu EN PYTHON (cf. docstring du module), comme load_data.py.

    `ultraperipherique` n'est PAS un détail : une RUP est à 85 % quelle que soit
    sa catégorie de base (art. 349 TFUE). L'oublier — ce que ce script a fait
    dans sa première version — donne 60 % à la Martinique au lieu de 85 %, et
    classe 28 opérations en dépassement de plafond alors qu'elles sont dans les
    clous. Aucune erreur n'est levée : le SQL tourne, les totaux sont justes,
    seul un booléen métier bascule. C'est l'oracle PostgreSQL (les vues
    existantes) qui l'a attrapé, pas `dbt test` ni l'oracle DuckDB — lequel ne
    couvre pas le cofinancement.
    """
    with open(DATA / "region_metadata.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "categorie_ue", "plafond_cofinancement"])
        n = 0
        for region, meta in data.items():
            if not isinstance(meta, dict):
                continue
            categorie = meta.get("categorie_ue")
            rup = bool(meta.get("ultraperipherique"))
            plafond = plafond_categorie(categorie, ultraperipherique=rup)
            w.writerow([region, categorie, "" if plafond is None else plafond])
            n += 1
    print(f"  {sortie.relative_to(DBT_DIR)} ({n} lignes)")


# Sources couvertes par le spike. Les cinq de 2014-2020 servent la SONDE
# (issue #135, étape 6) : elles ne sont là que pour construire
# `perimetre_2014_2020` et mesurer si les règles de substitution/addition
# passent en SQL portable — pas pour migrer la période.
SOURCES_DU_SPIKE = [
    ("2021-2027-conventionnees", "2021-2027", "2021-2027", "data.parquet"),
    ("2014-2020-synergie", "2014-2020", "2014-2020", "data_2014-2020.parquet"),
    ("2014-2020-pon-fse", "2014-2020-pon-fse", "2014-2020", "data_2014-2020_pon_fse.parquet"),
    ("2014-2020-normandie", "2014-2020-normandie", "2014-2020", "data_2014-2020_normandie.parquet"),
    (
        "2014-2020-nouvelle-aquitaine",
        "2014-2020-nouvelle-aquitaine",
        "2014-2020",
        "data_2014-2020_nouvelle_aquitaine.parquet",
    ),
    (
        "2014-2020-bretagne-officiel",
        "2014-2020-bretagne-officiel",
        "2014-2020",
        "data_2014-2020_bretagne_officiel.parquet",
    ),
]


def nom_modele(source_id):
    return "stg_operations_" + source_id.replace("-", "_")


if __name__ == "__main__":
    print("Modèles de staging :")
    for source_id, cle_schema, periode, fichier in SOURCES_DU_SPIKE:
        generer_staging(
            source_id=source_id,
            cle_schema=cle_schema,
            periode=periode,
            parquet=DATA / fichier,
            sortie=DBT_DIR / "models" / "staging" / f"{nom_modele(source_id)}.sql",
        )
    print("Seeds :")
    generer_seed_programme_totals(DBT_DIR / "seeds" / "programme_totals.csv")
    generer_seed_region_metadata(DBT_DIR / "seeds" / "region_metadata.csv")
