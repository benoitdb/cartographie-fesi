-- `engage_by_perimetre_fonds`, augmenté du comptage d'opérations que porte déjà
-- le côté 2014-2020 — nécessaire à `engage_all`, qui unionne les deux.
--
-- Les TROIS partitions d'`agregats.py` sont exclusives et doivent toutes être
-- portées : `v_engage_all` en avait oublié l'interrégional et s'arrêtait
-- 1,625 M€ trop bas (13 opérations, 0,02 % — assez peu pour passer inaperçu,
-- assez pour faire mentir un KPI).
SELECT periode, region AS perimetre, fonds,
       SUM(n_operations) AS n_operations,
       SUM(montant_ue_total) AS engage
FROM {{ ref('by_region_fonds') }}
GROUP BY periode, region, fonds

UNION ALL

SELECT periode, 'national' AS perimetre, fonds,
       COUNT(*) AS n_operations, SUM(montant_ue) AS engage
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE is_national AND fonds IS NOT NULL
GROUP BY periode, fonds

UNION ALL

SELECT periode, 'interregional' AS perimetre, fonds,
       COUNT(*) AS n_operations, SUM(montant_ue) AS engage
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE is_interregional AND fonds IS NOT NULL
GROUP BY periode, fonds
