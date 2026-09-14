-- Le taux de consommation vaut engage / programme quand programme > 0, 0 sinon.
-- Jamais plafonné : un dépassement est un signal, pas une anomalie.
-- Un écart > 1e-6 relatif signale une formule divergente entre les deux côtés
-- de pilotage_all.
SELECT periode, perimetre, fonds, taux, engage, programme,
       CASE WHEN programme > 0 THEN engage / programme ELSE 0 END AS taux_attendu
FROM {{ ref('pilotage_all') }}
WHERE ABS(
    taux - CASE WHEN programme > 0 THEN engage / programme ELSE 0 END
) > 1e-6
