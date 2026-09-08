-- Port de `v_engage_2014_2020` (04_periode_2014_2020.sql).
-- Part de `perimetre_2014_2020`, jamais des staging : c'est là que vivent la
-- substitution et l'addition, et les court-circuiter rétablirait le
-- double-comptage que #68/#95 ont motivé.
SELECT perimetre, fonds, COUNT(*) AS n_operations, SUM(montant_ue) AS engage
FROM {{ ref('perimetre_2014_2020') }}
WHERE fonds IS NOT NULL
GROUP BY perimetre, fonds
