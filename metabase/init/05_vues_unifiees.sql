-- Vues unifiées par période (issue #129) : socle de la réorganisation des
-- dashboards « par usage », où la période et le périmètre deviennent des
-- paramètres de dashboard au lieu d'écrans séparés.
--
-- PIÈGE CENTRAL, vérifié en chiffres avant d'écrire ce fichier — `v_pilotage`
-- et `v_engage_by_perimetre_fonds` (03_pilotage.sql) ne sont PAS scopées à
-- 2021-2027 : elles produisent aussi des lignes 2014-2020, en sommant
-- aveuglément les six sources qui se chevauchent sur cette période. C'est
-- exactement le double-comptage que #68/#95 ont motivé, et que la Phase 3 a
-- résolu dans `v_perimetre_2014_2020` (substitution Bretagne/Normandie/
-- Nouvelle-Aquitaine + addition PON FSE).
--
--   v_pilotage           2014-2020 -> 69 lignes, 20 057 M€  (faux : sources sommées)
--   v_pilotage_2014_2020 2014-2020 -> 55 lignes, 19 901 M€  (correct)
--
-- Unionner les deux telles quelles compterait donc la période 2014-2020 DEUX
-- fois (124 lignes, 39 958 M€). D'où le `WHERE periode = '2021-2027'` explicite
-- sur le côté 21-27 de chaque union ci-dessous : il n'est pas décoratif, il est
-- la condition de justesse.
--
-- Règle générale, reconduite de la Phase 3 : toute vue de fusion part des vues
-- de période (`v_*_2014_2020`), jamais d'`operations` ni des vues pilotage
-- génériques.

-- Engagé par (période, périmètre, fonds). Le côté 2021-2027 reprend la
-- structure de `v_engage_by_perimetre_fonds` en y ajoutant le comptage
-- d'opérations que porte déjà le côté 2014-2020.
CREATE OR REPLACE VIEW v_engage_all AS
SELECT
    periode,
    region AS perimetre,
    fonds,
    SUM(n_operations) AS n_operations,
    SUM(montant_ue_total) AS engage
FROM v_by_region_fonds
WHERE periode = '2021-2027'
GROUP BY periode, region, fonds
UNION ALL
SELECT
    periode,
    'national' AS perimetre,
    fonds,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS engage
FROM operations
WHERE is_national AND fonds IS NOT NULL AND periode = '2021-2027'
GROUP BY periode, fonds
UNION ALL
SELECT
    '2014-2020' AS periode,
    perimetre,
    fonds,
    n_operations,
    engage
FROM v_engage_2014_2020;

-- Programmé vs engagé par (période, périmètre, fonds). Les deux côtés portent
-- déjà la même formule (#62 : reste à engager calculé par fonds puis planché à
-- 0, taux jamais plafonné) — l'union ne recalcule rien, elle empile.
CREATE OR REPLACE VIEW v_pilotage_all AS
SELECT
    periode,
    perimetre,
    fonds,
    programme,
    engage,
    taux,
    reste_a_engager
FROM v_pilotage
WHERE periode = '2021-2027'
UNION ALL
SELECT
    '2014-2020' AS periode,
    perimetre,
    fonds,
    programme,
    engage,
    taux,
    reste_a_engager
FROM v_pilotage_2014_2020;
