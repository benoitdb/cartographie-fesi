-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2014-2020-pon-fse').
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

{% if target.type == 'duckdb' %}
SELECT
    '2014-2020-pon-fse' AS source_id,
    '2014-2020' AS periode,
    "num_dossier" AS numero_operation,
    "Libellé_po" AS libelle_programme,
    "Lib_opé" AS intitule_projet,
    "Lib_org" AS nom_beneficiaire,
    TRY_CAST("Dépenses totales" AS NUMERIC) AS depenses_eligibles,
    TRY_CAST("Mont_UE" AS NUMERIC) AS montant_ue,
    TRY_CAST("Date début réalisation" AS DATE) AS date_debut,
    TRY_CAST("Date fin réalisation" AS DATE) AS date_fin,
    "Fonds" AS fonds,
    CAST(NULL AS VARCHAR) AS numcci,
    CAST(NULL AS VARCHAR) AS resume_operation,
    CAST(NULL AS VARCHAR) AS cp_beneficiaire,
    CAST(NULL AS VARCHAR) AS cp_operation,
    CAST(NULL AS VARCHAR) AS zone,
    CAST(NULL AS VARCHAR) AS departement,
    CAST(NULL AS VARCHAR) AS pays,
    CAST(NULL AS VARCHAR) AS objectif_strategique,
    CAST(NULL AS VARCHAR) AS objectif_specifique,
    CAST(NULL AS VARCHAR) AS domaine_intervention,
    CAST(NULL AS VARCHAR) AS type_intervention,
    CAST(NULL AS NUMERIC) AS taux_cofinancement,
    CAST(NULL AS DATE) AS date_convention,
    CAST(NULL AS DATE) AS date_programmation,
    regions_source AS region_source,
    regions_modernes[1] AS region,
    regions_modernes AS regions_modernes,
    is_interregional AS is_interregional,
    is_national AS is_national
FROM read_parquet('{{ var("chemin_data") }}/data_2014-2020_pon_fse.parquet')
{% else %}
SELECT
    source_id,
    periode,
    numero_operation,
    libelle_programme,
    intitule_projet,
    nom_beneficiaire,
    depenses_eligibles,
    montant_ue,
    date_debut,
    date_fin,
    fonds,
    numcci,
    resume_operation,
    cp_beneficiaire,
    cp_operation,
    zone,
    departement,
    pays,
    objectif_strategique,
    objectif_specifique,
    domaine_intervention,
    type_intervention,
    taux_cofinancement,
    date_convention,
    date_programmation,
    region_source,
    region,
    regions_modernes,
    is_interregional,
    is_national
FROM {{ source('fesi', 'operations') }}
WHERE source_id = '2014-2020-pon-fse'
{% endif %}
