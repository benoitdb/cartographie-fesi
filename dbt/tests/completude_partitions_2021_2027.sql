-- Les trois partitions d'agregats.py (mono-région, national, interrégional) sont
-- exclusives et exhaustives : leur somme par fonds doit valoir by_fonds.
-- Un écart > 0,01 € signale une partition oubliée ou un filtre mal posé —
-- c'est le contrôle qui avait attrapé les 13 opérations interrégionales
-- manquantes de v_engage_all (1,625 M€, issue #138).
WITH partitions AS (
    SELECT fonds, SUM(engage) AS total
    FROM {{ ref('engage_by_perimetre_fonds') }}
    GROUP BY fonds
),
reference AS (
    SELECT fonds, SUM(montant_ue_total) AS total
    FROM {{ ref('by_fonds') }}
    GROUP BY fonds
)
SELECT r.fonds,
       r.total AS by_fonds,
       COALESCE(p.total, 0) AS somme_partitions,
       ABS(r.total - COALESCE(p.total, 0)) AS ecart
FROM reference r
LEFT JOIN partitions p ON p.fonds = r.fonds
WHERE ABS(r.total - COALESCE(p.total, 0)) > 0.01
