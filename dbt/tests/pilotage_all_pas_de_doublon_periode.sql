-- Même garde que sur engage_all : un couple (périmètre, fonds) ne doit
-- apparaître qu'une fois par période dans la vue unifiée de pilotage.
SELECT periode, perimetre, fonds, COUNT(*) AS nb
FROM {{ ref('pilotage_all') }}
GROUP BY periode, perimetre, fonds
HAVING COUNT(*) > 1
