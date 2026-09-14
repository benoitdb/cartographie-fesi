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
-- Interrégional 2021-2027 : troisième partition d'`agregats.py`, sans laquelle
-- la somme des périmètres ne redonnerait PAS le total de la source. Mesuré :
-- 13 opérations, 1,625 M€ — v_engage_all s'arrêtait à 7 878,196 M€ contre
-- 7 879,821 M€ pour `v_by_fonds`, un écart de 0,02 % assez petit pour passer
-- inaperçu à l'oeil et assez réel pour faire diverger un KPI unifié de son
-- équivalent Streamlit (issue #129, phase « charpente »).
--
-- Pas d'équivalent 2014-2020 : `v_perimetre_2014_2020` ne porte pas
-- l'interrégional Synergie (cf. son en-tête), et la page Streamlit de cette
-- période ne le compte pas non plus. L'asymétrie entre les deux périodes est
-- donc celle des deux écrans d'origine, pas un oubli d'ici.
SELECT
    periode,
    'interregional' AS perimetre,
    fonds,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS engage
FROM operations
WHERE is_interregional AND fonds IS NOT NULL AND periode = '2021-2027'
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

-- ---------------------------------------------------------------------------
-- Phase B (#129), suite : répartition thématique et cofinancement unifiés.
-- ---------------------------------------------------------------------------

-- Répartition thématique par (période, périmètre, fonds, niveau1, niveau2).
--
-- Les deux périodes ne décrivent PAS la même chose et ce n'est pas rattrapable
-- ici : 2021-2027 a une hiérarchie à deux étages (objectif stratégique ->
-- objectif spécifique), 2014-2020 a une dimension plate (domaine
-- d'intervention, cf. CLAUDE.md : jamais assimilée à un objectif stratégique).
-- D'où `niveau1`/`niveau2` plutôt que des noms de période, et `niveau2` NULL
-- sur tout le côté 14-20 — l'union rend l'asymétrie visible au lieu de la
-- masquer sous un libellé commun.
--
-- COUVERTURE, mesurée avant d'écrire cette vue (elle est très inégale et c'est
-- le fait le plus important à connaître avant d'en tirer un graphique) :
--   2021-2027 : objectif_strategique renseigné sur 16 619 / 16 625 opérations ;
--   2014-2020 : domaine_intervention renseigné sur 6 269 opérations, 1 991 M€ —
--     soit 9,7 % des 20 494 M€ de la période. Il n'est porté QUE par les trois
--     fichiers régionaux (Bretagne officiel, Normandie, Nouvelle-Aquitaine) ;
--     Synergie et le PON FSE, qui font les 90 % restants, ne le portent pas
--     du tout.
-- La dimension absente devient `'Non renseigné'` au lieu d'être filtrée : sans
-- ça, un treemap 2014-2020 afficherait 1 991 M€ là où la période en vaut
-- 20 494, sans que rien à l'écran ne dise où sont passés les 90 % manquants.
-- C'est aussi ce qui rend le contrôle de complétude possible (voir
-- verify_vues_unifiees.py, point 5) : regroupée par (période, périmètre,
-- fonds), cette vue doit redonner `v_engage_all` ligne à ligne. Les filtres
-- `fonds IS NOT NULL` et les trois partitions ci-dessous sont donc calqués sur
-- ceux de `v_engage_all`, pas choisis indépendamment.
CREATE OR REPLACE VIEW v_repartition_all AS
SELECT
    periode,
    region AS perimetre,
    fonds,
    COALESCE(objectif_strategique, 'Non renseigné') AS niveau1,
    COALESCE(objectif_specifique, 'Non renseigné') AS niveau2,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS engage
FROM operations
WHERE periode = '2021-2027'
  AND NOT is_interregional AND NOT is_national
  AND region IS NOT NULL AND fonds IS NOT NULL
GROUP BY periode, region, fonds, 4, 5
UNION ALL
SELECT
    periode,
    'national' AS perimetre,
    fonds,
    COALESCE(objectif_strategique, 'Non renseigné'),
    COALESCE(objectif_specifique, 'Non renseigné'),
    COUNT(*),
    SUM(montant_ue)
FROM operations
WHERE periode = '2021-2027' AND is_national AND fonds IS NOT NULL
GROUP BY periode, fonds, 4, 5
UNION ALL
SELECT
    periode,
    'interregional' AS perimetre,
    fonds,
    COALESCE(objectif_strategique, 'Non renseigné'),
    COALESCE(objectif_specifique, 'Non renseigné'),
    COUNT(*),
    SUM(montant_ue)
FROM operations
WHERE periode = '2021-2027' AND is_interregional AND fonds IS NOT NULL
GROUP BY periode, fonds, 4, 5
UNION ALL
-- Côté 2014-2020 : part de `v_perimetre_2014_2020` (qui porte désormais
-- `domaine_intervention`, cf. 04_periode_2014_2020.sql), jamais d'`operations`
-- — règle générale de ce fichier.
SELECT
    '2014-2020' AS periode,
    perimetre,
    fonds,
    COALESCE(domaine_intervention, 'Non renseigné'),
    NULL AS niveau2,
    COUNT(*),
    SUM(montant_ue)
FROM v_perimetre_2014_2020
WHERE fonds IS NOT NULL
GROUP BY perimetre, fonds, 4;

-- Plafond de cofinancement 2021-2027 par région, résolu EN PYTHON au
-- chargement (load_data.py appelle `dashboard/utils/cofinancement.
-- plafond_categorie`), pas recalculé ici : une région sur dix-neuf porte une
-- catégorie mixte — « Mixte : 57% Plus développée / 43% En transition (FEDER) »
-- pour Auvergne-Rhône-Alpes — dont le plafond est une moyenne pondérée extraite
-- du libellé par expression régulière. La transcrire en SQL en ferait une
-- seconde implémentation à maintenir. Même arbitrage, et pour la même raison,
-- que `categories_ue_2014_2020.plafond_min/max` (04_periode_2014_2020.sql).
--
-- La colonne est ajoutée ici et non dans `01_schema.sql` : ce dernier ne
-- s'exécute qu'à la création du volume Docker, donc l'y mettre seule laisserait
-- toute instance déjà provisionnée sans la colonne (cf. README, « Rejouer les
-- fichiers init »). `IF NOT EXISTS` rend ce fichier rejouable dans les deux cas.
ALTER TABLE region_metadata ADD COLUMN IF NOT EXISTS plafond_cofinancement NUMERIC;

-- Allocation additionnelle ultrapériphérique (RUP, art. 349 TFUE), 2021-2027 :
-- une dotation SUPPLÉMENTAIRE, distincte de la dotation de catégorie de base,
-- pour les sept périmètres qui y ont droit (les cinq DROM, Saint-Martin, et le
-- volet national côté FSE+). Lue dans `programme_detail.json` clé `rup` —
-- jusqu'ici le seul agrégat de `programme_detail.json` qu'aucune table SQL ne
-- portait, alors que l'écran régional Streamlit l'affiche déjà (#129, phase B).
--
-- Elle n'est PAS soustraite de `programme_totals` ni ajoutée dessus : le total
-- programmé de la région la contient déjà, et l'isoler ici sert à répondre
-- « combien de cette enveloppe tient à la seule ultrapériphéricité », pas à
-- corriger un total. Un JOIN qui l'additionnerait à `v_pilotage_all`
-- doublerait la part RUP.
CREATE TABLE IF NOT EXISTS allocations_rup (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL DEFAULT '2021-2027',
    perimetre TEXT NOT NULL,
    fonds TEXT NOT NULL,
    montant_ue NUMERIC NOT NULL
);

-- Cofinancement 2021-2027 par opération, face au plafond de la catégorie de sa
-- région (règlement (UE) 2021/1060, art. 112). Pendant exact de
-- `v_cofinancement_2014_2020` (04_periode_2014_2020.sql) : mêmes colonnes,
-- mêmes conventions, pour que l'union plus bas n'ait rien à réconcilier.
--
-- Trois écarts avec la période précédente, tous dictés par les données :
--   - un plafond simple et non un intervalle (min/max) : en 2021-2027 une
--     région moderne = un programme = une catégorie, sauf la catégorie mixte
--     d'Auvergne-Rhône-Alpes déjà résolue en moyenne pondérée côté Python ;
--   - aucun fonds hors champ à écarter. `FONDS_HORS_PLAFOND` (FEDER REACT-EU,
--     IEJ, FEAD) ne décrit que des libellés 2014-2020 ; la période n'en porte
--     que trois, FEDER, FSE+ et FTJ, tous plafonnés. Le filtre est écrit quand
--     même, à l'identique, pour que la règle reste la même des deux côtés de
--     l'union et non « celle qui se trouvait utile pour cette période » ;
--   - `taux_declare` est renseigné sur les 16 625 opérations (contre 7 132 sur
--     56 896 en 2014-2020) : la source de cette période le porte partout.
-- Comme en 2014-2020, c'est le taux CALCULÉ (montant UE / dépenses éligibles)
-- qui fait foi pour le dépassement, `taux_declare` restant un signal de qualité
-- de source affiché à part.
--
-- Tolérance 1e-6 sur la comparaison au plafond : même valeur et même raison
-- qu'en 2014-2020 (#126), et surtout même valeur que
-- `dashboard/utils/stats.detect_cofinancement_superieur_plafond`, qui compare à
-- `plafond * (1 + TOLERANCE_RELATIVE_PLAFOND)` — sans quoi l'écran Streamlit et
-- cette vue classeraient différemment les opérations programmées pile au
-- plafond.
--
-- `perimetre = 'national'` et `'interregional'` n'ont pas de ligne dans
-- `region_metadata` : le JOIN les écarte, un plafond de catégorie de région
-- n'ayant pas de sens hors d'une région — exactement comme le volet national
-- 2014-2020.
CREATE OR REPLACE VIEW v_cofinancement_2021_2027 AS
SELECT
    o.numero_operation, o.region, o.fonds,
    o.montant_ue, o.depenses_eligibles,
    CASE WHEN o.depenses_eligibles > 0 THEN o.montant_ue / o.depenses_eligibles END AS taux,
    o.taux_cofinancement AS taux_declare,
    CASE
        WHEN o.depenses_eligibles > 0 AND o.taux_cofinancement IS NOT NULL
         AND ABS(o.montant_ue / o.depenses_eligibles - o.taux_cofinancement) > 0.01
        THEN TRUE ELSE FALSE
    END AS taux_divergent,
    r.categorie_ue, r.plafond_cofinancement AS plafond,
    CASE
        WHEN o.depenses_eligibles > 0 AND r.plafond_cofinancement IS NOT NULL
         AND o.montant_ue / o.depenses_eligibles > r.plafond_cofinancement * 1.000001
        THEN TRUE ELSE FALSE
    END AS depasse_plafond
FROM operations o
JOIN region_metadata r ON r.region = o.region
WHERE o.periode = '2021-2027'
  AND NOT o.is_interregional AND NOT o.is_national
  AND o.fonds NOT IN ('FEDER REACT-EU', 'IEJ', 'FEAD')
  AND o.montant_ue IS NOT NULL AND o.depenses_eligibles IS NOT NULL;

-- Cofinancement unifié par (période, région, fonds). Agrégé et non par
-- opération : les deux vues de période portent des colonnes de plafond
-- différentes par nature (un intervalle en 2014-2020, un point en 2021-2027),
-- et forcer l'union au niveau opération obligerait à choisir laquelle des deux
-- formes perdre. Ici `plafond_min`/`plafond_max` valent le même nombre côté
-- 2021-2027, ce qui est exact plutôt que dégradé.
CREATE OR REPLACE VIEW v_cofinancement_all AS
SELECT
    '2014-2020' AS periode,
    region, fonds, categorie_ue, plafond_min, plafond_max,
    n_operations, n_depassements, montant_depassements,
    n_taux_divergents, montant_taux_divergents
FROM v_cofinancement_2014_2020_summary
UNION ALL
SELECT
    '2021-2027' AS periode,
    region, fonds, categorie_ue, plafond AS plafond_min, plafond AS plafond_max,
    COUNT(*) AS n_operations,
    COUNT(*) FILTER (WHERE depasse_plafond) AS n_depassements,
    COALESCE(SUM(montant_ue) FILTER (WHERE depasse_plafond), 0) AS montant_depassements,
    COUNT(*) FILTER (WHERE taux_divergent) AS n_taux_divergents,
    COALESCE(SUM(montant_ue) FILTER (WHERE taux_divergent), 0) AS montant_taux_divergents
FROM v_cofinancement_2021_2027
GROUP BY region, fonds, categorie_ue, plafond;
