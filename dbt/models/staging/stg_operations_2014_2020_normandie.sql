-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2014-2020-normandie').
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
    '2014-2020-normandie' AS source_id,
    '2014-2020' AS periode,
    "n° Dossier" AS numero_operation,
    "Intitulé du projet - Operation name" AS intitule_projet,
    "Nom du bénéficiaire - Beneficiary name" AS nom_beneficiaire,
    "CP / zip code" AS cp_beneficiaire,
    "Contexte, présentation générale de l'opération" AS resume_operation,
    TRY_CAST("Total des dépenses éligibles - Total eligible costs" AS NUMERIC) AS depenses_eligibles,
    TRY_CAST("Montant UE programmé" AS NUMERIC) AS montant_ue,
    TRY_CAST("taux de cofinancement UE - EU co-financing rate" AS NUMERIC) AS taux_cofinancement,
    TRY_CAST("date début op. / start" AS DATE) AS date_debut,
    TRY_CAST("date fin d'op. / end" AS DATE) AS date_fin,
    "Catégorie d'intervention - Intervention field" AS domaine_intervention,
    "Fond" AS fonds,
    "Libellé programme" AS libelle_programme,
    CAST(NULL AS VARCHAR) AS numcci,
    CAST(NULL AS VARCHAR) AS cp_operation,
    CAST(NULL AS VARCHAR) AS zone,
    CAST(NULL AS VARCHAR) AS departement,
    CAST(NULL AS VARCHAR) AS pays,
    CAST(NULL AS VARCHAR) AS objectif_strategique,
    CAST(NULL AS VARCHAR) AS objectif_specifique,
    CAST(NULL AS VARCHAR) AS type_intervention,
    CAST(NULL AS DATE) AS date_convention,
    CAST(NULL AS DATE) AS date_programmation,
    regions_source AS region_source,
    regions_modernes[1] AS region,
    regions_modernes AS regions_modernes,
    is_interregional AS is_interregional,
    is_national AS is_national
FROM read_parquet('{{ var("chemin_data") }}/data_2014-2020_normandie.parquet')
{% else %}
SELECT
    source_id,
    periode,
    numero_operation,
    intitule_projet,
    nom_beneficiaire,
    cp_beneficiaire,
    resume_operation,
    depenses_eligibles,
    montant_ue,
    taux_cofinancement,
    date_debut,
    date_fin,
    domaine_intervention,
    fonds,
    libelle_programme,
    numcci,
    cp_operation,
    zone,
    departement,
    pays,
    objectif_strategique,
    objectif_specifique,
    type_intervention,
    date_convention,
    date_programmation,
    region_source,
    region,
    regions_modernes,
    is_interregional,
    is_national
FROM {{ source('fesi', 'operations') }}
WHERE source_id = '2014-2020-normandie'
{% endif %}
