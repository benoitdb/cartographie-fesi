-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2014-2020-nouvelle-aquitaine').
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
    '2014-2020-nouvelle-aquitaine' AS source_id,
    '2014-2020' AS periode,
    "Colonne à masquer lors de la diffusion" AS libelle_programme,
    "Operation number" AS numero_operation,
    "Beneficiary name" AS nom_beneficiaire,
    "Operation name" AS intitule_projet,
    "Operation summary" AS resume_operation,
    "Funds" AS fonds,
    "Operation start date" AS date_debut,
    "Operation end date" AS date_fin,
    "Total amount programmed" AS depenses_eligibles,
    "Amount co-financing European Union" AS montant_ue,
    "Union co-financing rate (%)" AS taux_cofinancement,
    "Country" AS pays,
    "Name of category of intervention for the operation" AS domaine_intervention,
    CAST(NULL AS VARCHAR) AS numcci,
    CAST(NULL AS VARCHAR) AS cp_beneficiaire,
    CAST(NULL AS VARCHAR) AS cp_operation,
    CAST(NULL AS VARCHAR) AS zone,
    CAST(NULL AS VARCHAR) AS departement,
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
FROM read_parquet('{{ var("chemin_data") }}/data_2014-2020_nouvelle_aquitaine.parquet')
{% else %}
SELECT
    source_id,
    periode,
    libelle_programme,
    numero_operation,
    nom_beneficiaire,
    intitule_projet,
    resume_operation,
    fonds,
    date_debut,
    date_fin,
    depenses_eligibles,
    montant_ue,
    taux_cofinancement,
    pays,
    domaine_intervention,
    numcci,
    cp_beneficiaire,
    cp_operation,
    zone,
    departement,
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
WHERE source_id = '2014-2020-nouvelle-aquitaine'
{% endif %}
