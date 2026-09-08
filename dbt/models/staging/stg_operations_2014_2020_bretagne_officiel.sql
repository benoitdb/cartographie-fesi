-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2014-2020-bretagne-officiel').
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
    '2014-2020-bretagne-officiel' AS source_id,
    '2014-2020' AS periode,
    "No Dossier" AS numero_operation,
    "Fonds" AS fonds,
    "Bénéficiaire" AS nom_beneficiaire,
    "Nom de l'opération" AS intitule_projet,
    "Objectif de l'opération et réalisations escomptées" AS resume_operation,
    "Date de début de l'opération" AS date_debut,
    "Date de fin de l'opération" AS date_fin,
    "Cout total de l'opération" AS depenses_eligibles,
    "Taux de cofinancement par l'UE" AS taux_cofinancement,
    "Code Postal" AS cp_beneficiaire,
    "Pays" AS pays,
    "Domaine d'intervention" AS domaine_intervention,
    "Libellé programme" AS libelle_programme,
    "Montant UE" AS montant_ue,
    CAST(NULL AS VARCHAR) AS numcci,
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
FROM read_parquet('{{ var("chemin_data") }}/data_2014-2020_bretagne_officiel.parquet')
{% else %}
SELECT
    source_id,
    periode,
    numero_operation,
    fonds,
    nom_beneficiaire,
    intitule_projet,
    resume_operation,
    date_debut,
    date_fin,
    depenses_eligibles,
    taux_cofinancement,
    cp_beneficiaire,
    pays,
    domaine_intervention,
    libelle_programme,
    montant_ue,
    numcci,
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
WHERE source_id = '2014-2020-bretagne-officiel'
{% endif %}
