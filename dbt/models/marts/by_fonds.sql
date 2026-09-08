-- Port de `v_by_fonds` (02_views.sql). Dimension non géographique : porte sur
-- TOUTES les opérations de la source, les trois partitions confondues.
SELECT
    source_id, periode, fonds,
    {{ resume() }}
FROM {{ ref('stg_operations_2021_2027') }}
WHERE fonds IS NOT NULL
GROUP BY source_id, periode, fonds
