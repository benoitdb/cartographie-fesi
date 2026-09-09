-- Port de `v_pilotage_all` (05_vues_unifiees.sql). Les deux côtés portent déjà
-- la même formule (#62) — l'union ne recalcule rien, elle empile.
SELECT periode, perimetre, fonds, programme, engage, taux, reste_a_engager
FROM {{ ref('pilotage') }}

UNION ALL

SELECT '2014-2020' AS periode, perimetre, fonds, programme, engage, taux, reste_a_engager
FROM {{ ref('pilotage_2014_2020') }}
