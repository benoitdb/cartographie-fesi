-- Port de `v_engage_by_perimetre_fonds` (03_pilotage.sql), scopé 2021-2027.
--
-- La troisième partition (interrégional) est incluse ici, à la différence de
-- l'original : `v_engage_all` l'avait oubliée et s'arrêtait 1,625 M€ trop bas
-- (13 opérations, 0,02 % — assez peu pour passer inaperçu, assez pour faire
-- mentir un KPI, cf. 05_vues_unifiees.sql). Les trois partitions d'agregats.py
-- sont exclusives : une vue qui se veut le total d'une période doit les porter
-- toutes les trois.
SELECT periode, region AS perimetre, fonds, SUM(montant_ue_total) AS engage
FROM {{ ref('by_region_fonds') }}
GROUP BY periode, region, fonds

UNION ALL

SELECT periode, 'national' AS perimetre, fonds, SUM(montant_ue) AS engage
FROM {{ ref('stg_operations_2021_2027') }}
WHERE is_national AND fonds IS NOT NULL
GROUP BY periode, fonds

UNION ALL

SELECT periode, 'interregional' AS perimetre, fonds, SUM(montant_ue) AS engage
FROM {{ ref('stg_operations_2021_2027') }}
WHERE is_interregional AND fonds IS NOT NULL
GROUP BY periode, fonds
