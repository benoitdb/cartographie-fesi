-- Vues pilotage (Phase 2, issue #121) : programmé vs engagé par périmètre (région
-- ou 'national', clé déjà partagée par programme_totals — cf. dashboard/utils/pilotage.py)
-- et par fonds. Reproduit les deux règles de dashboard/utils/pilotage.py :
--   - taux_consommation = engage / programme, 0 si rien de programmé, jamais plafonné
--     (un dépassement est un signal à afficher, pas une anomalie, cf. CLAUDE.md) ;
--   - reste_a_engager se calcule PAR FONDS puis se plancher à 0 avant de sommer —
--     jamais programme_total - engage_total, qui laisserait un dépassement sur un
--     fonds ronger le reliquat des autres (issue #62, cas constaté sur
--     Auvergne-Rhône-Alpes : 94% consommé au global masquait ~150 M€ de FEDER
--     restant, le dépassement FSE+ absorbant le reliquat dans l'agrégat).
--
-- Scopée à 2021-2027 en pratique (comme le reste de la Phase 2, cf. #123) : elle
-- agrège l'engagé par périmètre/fonds SANS distinguer les sources d'une période,
-- ce qui reproduirait le double-comptage que #68/#95 ont motivé côté vues de
-- base (02_views.sql) si on l'utilisait telle quelle sur 2014-2020 (5 sources
-- qui se chevauchent). 2021-2027 n'a qu'une source, donc pas d'ambiguïté ici —
-- la fusion multi-sources par période reste un sujet de Phase 3.

CREATE VIEW v_engage_by_perimetre_fonds AS
SELECT periode, region AS perimetre, fonds, SUM(montant_ue_total) AS engage
FROM v_by_region_fonds
GROUP BY periode, region, fonds
UNION ALL
SELECT periode, 'national' AS perimetre, fonds, SUM(montant_ue) AS engage
FROM operations
WHERE is_national AND fonds IS NOT NULL
GROUP BY periode, fonds;

CREATE VIEW v_pilotage AS
SELECT
    p.periode,
    p.region AS perimetre,
    p.fonds,
    COALESCE(e.engage, 0) AS engage,
    p.montant_ue AS programme,
    CASE WHEN p.montant_ue > 0 THEN COALESCE(e.engage, 0) / p.montant_ue ELSE 0 END AS taux,
    GREATEST(p.montant_ue - COALESCE(e.engage, 0), 0) AS reste_a_engager
FROM programme_totals p
LEFT JOIN v_engage_by_perimetre_fonds e
    ON e.periode = p.periode AND e.perimetre = p.region AND e.fonds = p.fonds;
