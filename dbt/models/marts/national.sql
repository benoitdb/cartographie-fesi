-- Port de `v_national` (02_views.sql).
SELECT
    source_id, periode,
    {{ resume() }}
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE is_national
GROUP BY source_id, periode
