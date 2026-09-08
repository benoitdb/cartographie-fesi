-- Port de `v_by_region_fonds` (02_views.sql). Deux mesures seulement, comme
-- l'original — pas de moyennes ici.
SELECT
    source_id, periode, region, fonds,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total
FROM {{ ref('stg_operations_2021_2027') }}
WHERE NOT is_interregional AND NOT is_national AND region IS NOT NULL AND fonds IS NOT NULL
GROUP BY source_id, periode, region, fonds
