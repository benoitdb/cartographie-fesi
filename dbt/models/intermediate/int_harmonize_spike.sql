-- Spike #140 : vérification que l'harmonisation SQL reproduit le Python.
--
-- Ce modèle calcule l'harmonisation en SQL pour TOUTES les sources, et
-- conserve les colonnes Python à côté pour comparaison par le harnais
-- `verifier_harmonisation.py`.
--
-- DuckDB uniquement — côté PostgreSQL les colonnes harmonisées sont déjà
-- dans la table `operations` (chargées par `load_data.py`), donc le portage
-- n'y ajoute rien. C'est un des enseignements du spike.

{% if target.type == 'duckdb' %}

WITH
all_ops AS (
    SELECT
        source_id,
        row_number() OVER () AS row_id,
        region_source,
        libelle_programme,
        regions_modernes AS python_regions,
        is_interregional AS python_interregional,
        is_national AS python_national,
        periode
    FROM (
        SELECT * FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
        UNION ALL
        SELECT * FROM {{ ref('stg_operations_2014_2020_synergie') }}
        UNION ALL
        SELECT * FROM {{ ref('stg_operations_2014_2020_pon_fse') }}
        UNION ALL
        SELECT * FROM {{ ref('stg_operations_2014_2020_normandie') }}
        UNION ALL
        SELECT * FROM {{ ref('stg_operations_2014_2020_nouvelle_aquitaine') }}
        UNION ALL
        SELECT * FROM {{ ref('stg_operations_2014_2020_bretagne_officiel') }}
    )
),

normalised_ops AS (
    SELECT
        *,
        regexp_replace(
            trim(replace(replace(lower(COALESCE(libelle_programme, '')),
                chr(8217), chr(39)), chr(160), ' ')),
            ' +', ' ', 'g'
        ) AS libelle_programme_norm
    FROM all_ops
),

cas_vide AS (
    SELECT
        o.row_id,
        p.region AS prog_region,
        pi_agg.regions_list AS interreg_regions
    FROM normalised_ops o
    LEFT JOIN {{ ref('programme_to_region') }} p
        ON p.periode = o.periode
        AND p.libelle_programme = o.libelle_programme_norm
        AND p.region != ''
    LEFT JOIN (
        SELECT libelle_programme, list(region ORDER BY region) AS regions_list
        FROM {{ ref('programme_interregional') }}
        GROUP BY libelle_programme
    ) pi_agg ON pi_agg.libelle_programme = o.libelle_programme_norm
    WHERE o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = ''
),

fragments AS (
    SELECT
        o.row_id,
        trim(f.fragment) AS fragment
    FROM normalised_ops o,
    LATERAL unnest(string_split(CAST(o.region_source AS VARCHAR), ' | ')) AS f(fragment)
    WHERE o.region_source IS NOT NULL
      AND trim(CAST(o.region_source AS VARCHAR)) != ''
),

fragments_classes AS (
    SELECT
        row_id,
        fragment,
        CASE
            WHEN fragment = '' THEN 'vide'
            WHEN lower(fragment) IN (SELECT label FROM {{ ref('volet_national') }}) THEN 'national'
            WHEN fragment LIKE '%/%' THEN 'code_nom'
            ELSE 'bare'
        END AS type_fragment
    FROM fragments
),

fragments_resolus AS (
    SELECT
        fc.row_id,
        fc.type_fragment,
        CASE fc.type_fragment
            WHEN 'code_nom' THEN
                COALESCE(
                    c.region_moderne,
                    n.region_moderne,
                    trim(split_part(fc.fragment, '/', 2))
                )
            WHEN 'bare' THEN
                COALESCE(n.region_moderne, fc.fragment)
            ELSE NULL
        END AS region_moderne
    FROM fragments_classes fc
    LEFT JOIN {{ ref('code_to_region') }} c
        ON fc.type_fragment = 'code_nom'
        AND c.code = trim(split_part(fc.fragment, '/', 1))
    LEFT JOIN {{ ref('nom_to_region') }} n
        ON (fc.type_fragment = 'code_nom' AND n.nom = trim(split_part(fc.fragment, '/', 2)))
        OR (fc.type_fragment = 'bare' AND n.nom = fc.fragment)
    WHERE fc.type_fragment != 'vide'
),

cas_present AS (
    SELECT
        row_id,
        list_sort(list_distinct(
            list(region_moderne) FILTER (WHERE region_moderne IS NOT NULL)
        )) AS regions_list,
        bool_or(type_fragment = 'national') AS had_national,
        count(*) FILTER (WHERE type_fragment NOT IN ('national')) AS n_regions
    FROM fragments_resolus
    GROUP BY row_id
)

SELECT
    o.source_id,
    o.row_id,
    o.region_source,
    o.python_regions,
    o.python_interregional,
    o.python_national,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            CASE
                WHEN cv.prog_region IS NOT NULL THEN [cv.prog_region]
                WHEN cv.interreg_regions IS NOT NULL THEN cv.interreg_regions
                ELSE []::VARCHAR[]
            END
        WHEN cp.had_national AND cp.n_regions = 0 THEN []::VARCHAR[]
        ELSE COALESCE(cp.regions_list, []::VARCHAR[])
    END AS sql_regions,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            COALESCE(cv.interreg_regions IS NOT NULL, false)
        WHEN cp.had_national AND cp.n_regions = 0 THEN false
        ELSE COALESCE(len(cp.regions_list) > 1, false)
    END AS sql_interregional,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            cv.prog_region IS NULL AND cv.interreg_regions IS NULL
        WHEN cp.had_national AND cp.n_regions = 0 THEN true
        ELSE false
    END AS sql_national
FROM normalised_ops o
LEFT JOIN cas_vide cv ON cv.row_id = o.row_id
LEFT JOIN cas_present cp ON cp.row_id = o.row_id

{% else %}

-- PostgreSQL : pas de calcul, l'harmonisation est déjà dans la table operations.
SELECT
    NULL::VARCHAR AS source_id,
    0 AS row_id,
    NULL::VARCHAR AS region_source,
    NULL AS python_regions,
    false AS python_interregional,
    false AS python_national,
    NULL AS sql_regions,
    false AS sql_interregional,
    false AS sql_national
WHERE false

{% endif %}
