-- Le reste à engager est planché à 0 PAR FONDS (issue #62) : sommer
-- programme - engage sur les totaux laisserait un dépassement sur un fonds
-- ronger le reliquat des autres. Toute ligne négative trahit un GREATEST
-- manquant ou mal placé.
SELECT periode, perimetre, fonds, reste_a_engager
FROM {{ ref('pilotage_all') }}
WHERE reste_a_engager < 0
