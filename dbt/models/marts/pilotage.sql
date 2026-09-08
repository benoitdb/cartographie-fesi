-- Port de `v_pilotage` (03_pilotage.sql). Deux règles de dashboard/utils/pilotage.py :
--   - taux = engage / programme, 0 si rien de programmé, JAMAIS plafonné
--     (un dépassement est un signal à afficher, pas une anomalie) ;
--   - reste_a_engager calculé PAR FONDS puis planché à 0 — jamais
--     programme_total - engage_total, qui laisserait un dépassement sur un fonds
--     ronger le reliquat des autres (issue #62, cas Auvergne-Rhône-Alpes).
--
-- Le planchage par fonds est ici une propriété de la GRAIN de la table (une
-- ligne = un couple périmètre/fonds), pas d'un `GROUP BY` : sommer cette colonne
-- donne le bon total, sommer `programme - engage` ne le donnerait pas.
SELECT
    p.periode,
    p.region AS perimetre,
    p.fonds,
    COALESCE(e.engage, 0) AS engage,
    p.montant_ue AS programme,
    CASE WHEN p.montant_ue > 0 THEN COALESCE(e.engage, 0) / p.montant_ue ELSE 0 END AS taux,
    GREATEST(p.montant_ue - COALESCE(e.engage, 0), 0) AS reste_a_engager
FROM {{ ref('programme_totals') }} p
LEFT JOIN {{ ref('engage_by_perimetre_fonds') }} e
    ON e.periode = p.periode AND e.perimetre = p.region AND e.fonds = p.fonds
WHERE p.periode = '2021-2027'
