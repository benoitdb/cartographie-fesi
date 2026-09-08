-- Port de `v_interregional` (02_views.sql).
SELECT
    source_id, periode,
    {{ resume() }}
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE is_interregional
GROUP BY source_id, periode
