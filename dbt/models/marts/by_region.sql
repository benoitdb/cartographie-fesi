-- Port de `v_by_region` (metabase/init/02_views.sql).
-- Règle reprise telle quelle : by_region ne porte QUE la partition mono-région,
-- sinon une opération multi-régions serait comptée plusieurs fois dans un total
-- qui se veut une somme (cf. data-pipeline/agregats.py).
SELECT
    source_id, periode, region,
    {{ resume() }}
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE NOT is_interregional AND NOT is_national AND region IS NOT NULL
GROUP BY source_id, periode, region
