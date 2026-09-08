-- FICHIER GÉNÉRÉ par dbt/generer.py — ne pas éditer à la main.
-- Source de vérité : data-pipeline/schema_source.py (clé de schéma '2021-2027').
-- Voir la docstring de generer.py pour pourquoi ce SQL n'est pas écrit à la main.

SELECT
    '2021-2027-conventionnees' AS source_id,
    '2021-2027' AS periode,
    "Numéro Opération" AS numero_operation,
    "NUMCCI" AS numcci,
    "Libellé Programme" AS libelle_programme,
    "Intitulé du projet" AS intitule_projet,
    "Nom du bénéficiaire" AS nom_beneficiaire,
    "Code postal du bénéficiaire" AS cp_beneficiaire,
    "Date de début de l'opération" AS date_debut,
    "Date de fin de l'opération" AS date_fin,
    "Code postal de l’opération" AS cp_operation,
    "Zone" AS zone,
    "Département de l’opération" AS departement,
    "Pays" AS pays,
    "Type d'intervention" AS type_intervention,
    "Fonds" AS fonds,
    "Objectif spécifique" AS objectif_specifique,
    "Objectif stratégique" AS objectif_strategique,
    "Total des dépenses éligibles" AS depenses_eligibles,
    "Taux de cofinancement" AS taux_cofinancement,
    "Montant UE" AS montant_ue,
    "Date première convention" AS date_convention,
    regions_source AS region_source,
    regions_modernes[1] AS region,
    regions_modernes,
    is_interregional,
    is_national
FROM {% if target.type == 'duckdb' %}
    read_parquet('{{ var("chemin_data") }}/data.parquet')
{% else %}
    {{ source('fesi', 'operations') }} WHERE source_id = '2021-2027-conventionnees'
{% endif %}
