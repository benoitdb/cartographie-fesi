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

-- LES TROIS PARTITIONS D'`agregats.py` SONT EXCLUSIVES (mono-région,
-- interrégional, national) : une vue qui se veut « l'engagé par périmètre » doit
-- les porter toutes les trois, sinon sa somme n'est pas le total de la période.
-- Cette vue n'en portait que deux et perdait l'interrégional — 13 opérations,
-- 1,625 M€ sur 2021-2027, soit 0,02 % : assez peu pour passer inaperçu à l'oeil,
-- assez pour faire mentir un KPI (issue #138).
--
-- C'est le MÊME défaut que `v_engage_all` a connu et corrigé en phase #129 ; la
-- correction n'avait pas été reportée ici, faute d'un contrôle de complétude sur
-- cette vue-ci. `verify_vues_unifiees.py` en a désormais un (point 3 bis).
--
-- Sans effet sur `v_pilotage`, qui joint `programme_totals` : le périmètre
-- `interregional` n'y a aucune ligne d'enveloppe, le LEFT JOIN l'écarte. La
-- correction rétablit donc la justesse de cette vue lue seule, sans déplacer
-- aucun taux de consommation.
CREATE VIEW v_engage_by_perimetre_fonds AS
SELECT periode, region AS perimetre, fonds, SUM(montant_ue_total) AS engage
FROM v_by_region_fonds
GROUP BY periode, region, fonds
UNION ALL
SELECT periode, 'national' AS perimetre, fonds, SUM(montant_ue) AS engage
FROM operations
WHERE is_national AND fonds IS NOT NULL
GROUP BY periode, fonds
UNION ALL
SELECT periode, 'interregional' AS perimetre, fonds, SUM(montant_ue) AS engage
FROM operations
WHERE is_interregional AND fonds IS NOT NULL
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
