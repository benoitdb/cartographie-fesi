-- Port de `v_pilotage_2014_2020` (04_periode_2014_2020.sql).
-- Même formule que `pilotage` (2021-2027) : taux jamais plafonné, reste à
-- engager calculé PAR FONDS puis planché à 0 (#62).
--
-- FEAD et FEDER-FSE n'y apparaissent jamais : aucune ligne `programme_totals`
-- pour ces deux libellés (le premier hors Fonds ESI, le second pas un fonds
-- mais le libellé du PNAT Europ'Act).
SELECT
    ev.perimetre,
    ev.fonds,
    ev.programme,
    COALESCE(e.engage, 0) AS engage,
    CASE WHEN ev.programme > 0 THEN COALESCE(e.engage, 0) / ev.programme ELSE 0 END AS taux,
    GREATEST(ev.programme - COALESCE(e.engage, 0), 0) AS reste_a_engager
FROM {{ ref('enveloppes_2014_2020') }} ev
LEFT JOIN {{ ref('engage_2014_2020') }} e
    ON e.perimetre = ev.perimetre AND e.fonds = ev.fonds
