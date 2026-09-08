-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2014-2020').
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
    '2014-2020-synergie' AS source_id,
    '2014-2020' AS periode,
    "Numéro Opération" AS numero_operation,
    "NumCCI" AS numcci,
    "Libellé programme" AS libelle_programme,
    "Intitulé du projet" AS intitule_projet,
    "Résumé de l'opération" AS resume_operation,
    "Nom du bénéficiaire" AS nom_beneficiaire,
    "Code postal du bénéficiaire" AS cp_beneficiaire,
    "Date de début de l'opération" AS date_debut,
    "Date de fin de l'opération" AS date_fin,
    "Code postal de l’opération" AS cp_operation,
    "Zone" AS zone,
    "Département de l’opération" AS departement,
    "Pays" AS pays,
    "Domaine d’intervention" AS domaine_intervention,
    "Date de programmation" AS date_programmation,
    "Fonds" AS fonds,
    "Total des dépenses éligibles programmées" AS depenses_eligibles,
    "Montant UE programmé" AS montant_ue,
    CAST(NULL AS VARCHAR) AS objectif_strategique,
    CAST(NULL AS VARCHAR) AS objectif_specifique,
    CAST(NULL AS VARCHAR) AS type_intervention,
    CAST(NULL AS NUMERIC) AS taux_cofinancement,
    CAST(NULL AS DATE) AS date_convention,
    regions_source AS region_source,
    regions_modernes[1] AS region,
    regions_modernes AS regions_modernes,
    is_interregional AS is_interregional,
    is_national AS is_national
FROM read_parquet('{{ var("chemin_data") }}/data_2014-2020.parquet')
{% else %}
SELECT
    source_id,
    periode,
    numero_operation,
    numcci,
    libelle_programme,
    intitule_projet,
    resume_operation,
    nom_beneficiaire,
    cp_beneficiaire,
    date_debut,
    date_fin,
    cp_operation,
    zone,
    departement,
    pays,
    domaine_intervention,
    date_programmation,
    fonds,
    depenses_eligibles,
    montant_ue,
    objectif_strategique,
    objectif_specifique,
    type_intervention,
    taux_cofinancement,
    date_convention,
    region_source,
    region,
    regions_modernes,
    is_interregional,
    is_national
FROM {{ source('fesi', 'operations') }}
WHERE source_id = '2014-2020-synergie'
{% endif %}
