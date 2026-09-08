"""Génère le modèle de staging et les seeds du spike depuis le Python existant.

POURQUOI UN CODEGEN, ET PAS DU SQL ÉCRIT À LA MAIN — c'est le premier
enseignement du spike (issue #135).

Le renommage « libellé brut du fichier source → clé interne → colonne SQL » a
aujourd'hui trois descriptions (`schema_source.SCHEMAS`,
`periodes.RENOMMAGES`, `load_data.INTERNAL_KEY_TO_COLUMN`). Écrire le `SELECT
... AS ...` du staging à la main en ajouterait une **quatrième**, exactement le
défaut que dbt était censé corriger. Or dbt ne sait pas importer du Python :
ses macros sont du Jinja, et un `dbt-duckdb` peut certes exécuter du Python
dans un modèle, mais pas au moment où le SQL est *compilé*.

D'où ce script, lancé AVANT `dbt build`. Le SQL généré reste lisible et
versionnable ; la source de vérité reste `schema_source`.

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
sys.path.insert(0, str(REPO / "metabase"))

import schema_source  # noqa: E402

from utils.cofinancement import plafond_categorie  # noqa: E402

# Même table que `load_data.INTERNAL_KEY_TO_COLUMN` — importée plutôt que
# recopiée : c'est tout l'intérêt du codegen.
sys.path.insert(0, str(REPO / "metabase"))
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

ENTETE = """-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma {cle!r}).
-- Voir la docstring de generer.py pour pourquoi ce SQL n'est pas écrit à la main.
"""


def libelles_reels(parquet_path):
    """Libellés réels du Parquet, indexés par leur forme neutralisée."""
    colonnes = pd.read_parquet(parquet_path).columns
    return {schema_source.normalise_libelle(c): c for c in colonnes}


# LE POINT DE FORK entre les deux cibles, et le premier vrai coût mesuré du
# spike : côté DuckDB le staging lit le Parquet et fait le renommage ; côté
# PostgreSQL il n'a rien à renommer, parce que `metabase/load_data.py` l'a déjà
# fait au chargement. Les deux cibles ne partagent donc PAS la couche de
# staging — seulement les marts.
FROM_CIBLE = """
FROM {{% if target.type == 'duckdb' %}}
    read_parquet('{{{{ var("chemin_data") }}}}/{parquet}')
{{% else %}}
    {{{{ source('fesi', 'operations') }}}} WHERE source_id = '{source_id}'
{{% endif %}}
"""


def generer_staging(source_id, cle_schema, periode, parquet, sortie):
    reels = libelles_reels(parquet)
    lignes, manquantes = [], []
    for cle_interne, libelle_attendu in schema_source.schema_de_periode(cle_schema):
        colonne_sql = INTERNAL_KEY_TO_COLUMN.get(cle_interne)
        if colonne_sql is None:
            continue  # clé sans colonne dédiée (objectifs_desc, objectif_spec_lib) -> `extra`
        reel = reels.get(schema_source.normalise_libelle(libelle_attendu))
        if reel is None:
            manquantes.append(libelle_attendu)
            continue
        lignes.append(f'    "{reel}" AS {colonne_sql}')

    if manquantes:
        raise SystemExit(
            f"{source_id}: colonnes attendues absentes du Parquet : {manquantes}"
        )

    # `regions_modernes` / `is_interregional` / `is_national` sont posées par
    # ingest.py sur chaque opération, pas par le fichier source : elles ne sont
    # dans aucun schéma. `region` = regions_modernes[0], comme load_data.py.
    # `regions_modernes[1]` : indexation à 1 dans DuckDB comme dans PostgreSQL
    # (LIST et TEXT[]) — un des rares endroits où les deux dialectes coïncident
    # sans effort. `region` = première région, comme `load_data.py`.
    lignes += [
        "    regions_source AS region_source",
        "    regions_modernes[1] AS region",
        "    regions_modernes",
        "    is_interregional",
        "    is_national",
    ]

    sql = ENTETE.format(cle=cle_schema) + (
        f"\nSELECT\n    '{source_id}' AS source_id,\n"
        f"    '{periode}' AS periode,\n"
        + ",\n".join(lignes)
        + FROM_CIBLE.format(parquet=parquet.name, source_id=source_id)
    )
    sortie.write_text(sql, encoding="utf-8")
    print(f"  {sortie.relative_to(DBT_DIR)} ({len(lignes)} colonnes)")


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
    """Plafond résolu EN PYTHON (cf. docstring du module), comme load_data.py."""
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
            w.writerow([region, categorie, plafond_categorie(categorie) if categorie else ""])
            n += 1
    print(f"  {sortie.relative_to(DBT_DIR)} ({n} lignes)")


if __name__ == "__main__":
    print("Modèles de staging :")
    generer_staging(
        source_id="2021-2027-conventionnees",
        cle_schema="2021-2027",
        periode="2021-2027",
        parquet=DATA / "data.parquet",
        sortie=DBT_DIR / "models" / "staging" / "stg_operations_2021_2027.sql",
    )
    print("Seeds :")
    generer_seed_programme_totals(DBT_DIR / "seeds" / "programme_totals.csv")
    generer_seed_region_metadata(DBT_DIR / "seeds" / "region_metadata.csv")
