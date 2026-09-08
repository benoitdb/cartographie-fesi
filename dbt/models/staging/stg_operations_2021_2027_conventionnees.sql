-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2021-2027').
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
    '2021-2027-conventionnees' AS source_id,
    '2021-2027' AS periode,
    "Numéro Opération" AS numero_operation,
    "NUMCCI" AS numcci,
    "Libellé Programme" AS libelle_programme,
    "Intitulé du projet" AS intitule_projet,
    "Nom du bénéficiaire" AS nom_beneficiaire,
    "Code postal du bénéficiaire" AS cp_beneficiaire,
    TRY_CAST("Date de début de l'opération" AS DATE) AS date_debut,
    TRY_CAST("Date de fin de l'opération" AS DATE) AS date_fin,
    "Code postal de l’opération" AS cp_operation,
    "Zone" AS zone,
    "Département de l’opération" AS departement,
    "Pays" AS pays,
    "Type d'intervention" AS type_intervention,
    "Fonds" AS fonds,
    "Objectif spécifique" AS objectif_specifique,
    "Objectif stratégique" AS objectif_strategique,
    TRY_CAST("Total des dépenses éligibles" AS NUMERIC) AS depenses_eligibles,
    TRY_CAST("Taux de cofinancement" AS NUMERIC) AS taux_cofinancement,
    TRY_CAST("Montant UE" AS NUMERIC) AS montant_ue,
    TRY_CAST("Date première convention" AS DATE) AS date_convention,
    CAST(NULL AS VARCHAR) AS resume_operation,
    CAST(NULL AS VARCHAR) AS domaine_intervention,
    CAST(NULL AS DATE) AS date_programmation,
    regions_source AS region_source,
    regions_modernes[1] AS region,
    regions_modernes AS regions_modernes,
    is_interregional AS is_interregional,
    is_national AS is_national
FROM read_parquet('{{ var("chemin_data") }}/data.parquet')
{% else %}
SELECT
    source_id,
    periode,
    numero_operation,
    numcci,
    libelle_programme,
    intitule_projet,
    nom_beneficiaire,
    cp_beneficiaire,
    date_debut,
    date_fin,
    cp_operation,
    zone,
    departement,
    pays,
    type_intervention,
    fonds,
    objectif_specifique,
    objectif_strategique,
    depenses_eligibles,
    taux_cofinancement,
    montant_ue,
    date_convention,
    resume_operation,
    domaine_intervention,
    date_programmation,
    region_source,
    region,
    regions_modernes,
    is_interregional,
    is_national
FROM {{ source('fesi', 'operations') }}
WHERE source_id = '2021-2027-conventionnees'
{% endif %}
