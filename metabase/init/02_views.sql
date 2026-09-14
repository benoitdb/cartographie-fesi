-- Vues d'agrégats de base (Phase 0, issue #121), scopées par (source_id, periode)
-- plutôt que blended sur toute une période : Bretagne/Normandie/Nouvelle-Aquitaine
-- ont chacune leur propre fichier ET quelques opérations marginales dans Synergie
-- (cf. CLAUDE.md #68), et PON FSE se fusionne par opération dans les régions
-- existantes ou le national (#95) — sommer aveuglément across sources pour une
-- période compterait des opérations en double ou mal réparties. Chaque source
-- reste donc son propre périmètre agrégé, exactement comme `agregats.py` le fait
-- déjà : chaque fichier JSON porte ses propres `aggregates`, jamais un total
-- 2014-2020 unique. La fusion multi-sources reste un sujet de Phase 2/3
-- (vues pilotage), pas de ces vues de base.
--
-- Reproduit la règle de partitionnement d'`agregats.py` (data-pipeline/agregats.py) :
-- une opération appartient à une seule des trois partitions (mono-région,
-- interrégionale, national) ; by_region ne porte QUE sur la première, sinon une
-- opération multi-régions serait comptée plusieurs fois dans un total qui se
-- veut une somme. by_fonds et by_objectif_strategique portent, eux, sur TOUTES
-- les opérations d'une source (dimension non géographique).

CREATE VIEW v_by_region AS
SELECT
    source_id, periode, region,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
FROM operations
WHERE NOT is_interregional AND NOT is_national AND region IS NOT NULL
GROUP BY source_id, periode, region;

CREATE VIEW v_national AS
SELECT
    source_id, periode,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
FROM operations
WHERE is_national
GROUP BY source_id, periode;

CREATE VIEW v_interregional AS
SELECT
    source_id, periode,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
FROM operations
WHERE is_interregional
GROUP BY source_id, periode;

CREATE VIEW v_by_fonds AS
SELECT
    source_id, periode, fonds,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
FROM operations
WHERE fonds IS NOT NULL
GROUP BY source_id, periode, fonds;

CREATE VIEW v_by_region_fonds AS
SELECT
    source_id, periode, region, fonds,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total
FROM operations
WHERE NOT is_interregional AND NOT is_national AND region IS NOT NULL AND fonds IS NOT NULL
GROUP BY source_id, periode, region, fonds;

-- 2021-2027 uniquement en pratique : objectif_strategique est NULL pour toute
-- source 2014-2020 (cf. CLAUDE.md, la dimension thématique 14-20 est
-- domaine_intervention, jamais assimilée à un objectif stratégique).
CREATE VIEW v_by_objectif_strategique AS
SELECT
    source_id, periode, objectif_strategique,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
FROM operations
WHERE objectif_strategique IS NOT NULL
GROUP BY source_id, periode, objectif_strategique;
