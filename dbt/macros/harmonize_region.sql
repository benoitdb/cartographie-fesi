-- Harmonisation des régions en SQL — équivalent de region_mapping.harmonize_region.
--
-- Spike #140 : la cascade de résolution (code INSEE → nom ancien → bare → programme
-- → interrégional → national) est reproduite en jointures + agrégation. Validée à
-- zéro divergence sur 72 675 opérations (6 sources).
--
-- Le Parquet porte la colonne brute sous un nom différent par source (« Région de
-- l'opération », « Région », « Region_adm »). Le staging la renomme en
-- `region_source` avant d'appeler cette macro — c'est le contrat d'entrée.

{% macro harmonize_region(relation, periode) %}

WITH
source_ops AS (
    SELECT
        *,
        regexp_replace(
            trim(replace(replace(lower(COALESCE(libelle_programme, '')),
                chr(8217), chr(39)), chr(160), ' ')),
            ' +', ' ', 'g'
        ) AS libelle_programme_norm
    FROM {{ relation }}
),

-- Cas 1 : region_source NULL/vide → fallback programme mono-région, puis interrégional
cas_vide AS (
    SELECT
        o.row_id,
        p.region AS prog_region,
        pi_agg.regions_list AS interreg_regions
    FROM source_ops o
    LEFT JOIN {{ ref('programme_to_region') }} p
        ON p.periode = '{{ periode }}'
        AND p.libelle_programme = o.libelle_programme_norm
        AND p.region != ''
    LEFT JOIN (
        SELECT libelle_programme, list(region ORDER BY region) AS regions_list
        FROM {{ ref('programme_interregional') }}
        GROUP BY libelle_programme
    ) pi_agg ON pi_agg.libelle_programme = o.libelle_programme_norm
    WHERE o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = ''
),

-- Cas 2 : region_source présente → split | , lookup, re-agréger
fragments AS (
    SELECT
        o.row_id,
        trim(f.fragment) AS fragment
    FROM source_ops o,
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
    o.*,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            CASE
                WHEN cv.prog_region IS NOT NULL THEN [cv.prog_region]
                WHEN cv.interreg_regions IS NOT NULL THEN cv.interreg_regions
                ELSE []::VARCHAR[]
            END
        WHEN cp.had_national AND cp.n_regions = 0 THEN []::VARCHAR[]
        ELSE COALESCE(cp.regions_list, []::VARCHAR[])
    END AS regions_modernes_calc,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            COALESCE(cv.interreg_regions IS NOT NULL, false)
        WHEN cp.had_national AND cp.n_regions = 0 THEN false
        ELSE COALESCE(len(cp.regions_list) > 1, false)
    END AS is_interregional_calc,
    CASE
        WHEN o.region_source IS NULL OR trim(CAST(o.region_source AS VARCHAR)) = '' THEN
            cv.prog_region IS NULL AND cv.interreg_regions IS NULL
        WHEN cp.had_national AND cp.n_regions = 0 THEN true
        ELSE false
    END AS is_national_calc
FROM source_ops o
LEFT JOIN cas_vide cv ON cv.row_id = o.row_id
LEFT JOIN cas_present cp ON cp.row_id = o.row_id

{% endmacro %}
