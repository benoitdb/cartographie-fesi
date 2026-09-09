-- Port de `v_by_objectif_strategique` (02_views.sql).
SELECT
    source_id, periode, objectif_strategique,
    {{ resume() }}
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE objectif_strategique IS NOT NULL
GROUP BY source_id, periode, objectif_strategique
