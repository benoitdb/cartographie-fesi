-- Vues Phase 3 (issue #121) : dashboard 2014-2020, ce que Phase 1/2 avaient
-- laissé de côté (voir 03_pilotage.sql, dernier paragraphe de son en-tête).
--
-- `02_views.sql`/`03_pilotage.sql` restent scopées par (source_id, periode) ou
-- somment aveuglément toutes les sources d'une période : correct pour
-- 2021-2027 (une seule source), faux pour 2014-2020, qui en a six et se
-- chevauchent (#68/#95) :
--   - Bretagne (officiel), Normandie, Nouvelle-Aquitaine SE SUBSTITUENT à
--     Synergie sur leur région (leur périmètre Synergie n'est que marginal) ;
--   - le programme opérationnel national FSE (`2014-2020-pon-fse`) est
--     ADDITIF, routé par `libelle_programme` et non par la région portée sur
--     chaque ligne (`Region_adm`, remplie à 97 % mais qui ne sert pas de clé
--     de routage) : les cinq PO FSE État des DROM rejoignent leur région,
--     PON FSE et PO IEJ national rejoignent le volet national (#95, point 3,
--     cf. `dashboard/utils/periodes.REGIONS_PON_FSE_2014_2020`).
--
-- `v_perimetre_2014_2020` reproduit ces deux règles, opération par opération
-- (une ligne = une opération, taguée de son périmètre final) ; le reste de ce
-- fichier agrège dessus. Le vieux fichier Bretagne (`2014-2020-bretagne`,
-- europe.bzh) n'y figure jamais : remplacé par `2014-2020-bretagne-officiel`
-- pour tout usage autre que la page « Validation de la source ».

CREATE VIEW v_perimetre_2014_2020 AS
SELECT numero_operation, fonds, montant_ue, depenses_eligibles, perimetre
FROM (
    -- Synergie : périmètre régional, sauf les trois régions qui ont leur
    -- propre fichier (substitution, pas addition).
    SELECT numero_operation, fonds, montant_ue, depenses_eligibles, region AS perimetre
    FROM operations
    WHERE source_id = '2014-2020-synergie'
      AND NOT is_interregional AND NOT is_national
      AND region IS NOT NULL
      AND region NOT IN ('Bretagne', 'Normandie', 'Nouvelle-Aquitaine')

    UNION ALL

    -- Synergie : volet national, inchangé (mêmes opérations que v_national).
    SELECT numero_operation, fonds, montant_ue, depenses_eligibles, 'national' AS perimetre
    FROM operations
    WHERE source_id = '2014-2020-synergie' AND is_national

    UNION ALL

    -- Les trois fichiers régionaux hors-Synergie qui se substituent à Synergie
    -- sur leur région (#95) : chaque ligne y est de cette région par
    -- construction (pretraitement du pipeline), pas de filtre supplémentaire.
    SELECT numero_operation, fonds, montant_ue, depenses_eligibles, region AS perimetre
    FROM operations
    WHERE source_id IN ('2014-2020-normandie', '2014-2020-nouvelle-aquitaine', '2014-2020-bretagne-officiel')
      AND region IS NOT NULL

    UNION ALL

    -- PON FSE (#95, point 3) : additif, routé par PROGRAMME et non par région.
    -- REGIONS_PON_FSE_2014_2020 : 5 PO FSE État des DROM -> leur région ;
    -- PON FSE + PO IEJ national -> volet national.
    SELECT numero_operation, fonds, montant_ue, depenses_eligibles,
        CASE libelle_programme
            WHEN 'PO réunion' THEN 'La Réunion'
            WHEN 'PO Guadeloupe' THEN 'Guadeloupe'
            WHEN 'PO Martinique' THEN 'Martinique'
            WHEN 'PO Guyane' THEN 'Guyane'
            WHEN 'PO Mayotte' THEN 'Mayotte'
            ELSE 'national'
        END AS perimetre
    FROM operations
    WHERE source_id = '2014-2020-pon-fse'
) x;

CREATE VIEW v_engage_2014_2020 AS
SELECT perimetre, fonds, COUNT(*) AS n_operations, SUM(montant_ue) AS engage
FROM v_perimetre_2014_2020
WHERE fonds IS NOT NULL
GROUP BY perimetre, fonds;

-- Enveloppes 2014-2020, après fusion FEDER REACT-EU -> FEDER quand le
-- périmètre ne porte aucune opération étiquetée `FEDER REACT-EU` (seuls les
-- quatre DROM le font dans Synergie ; en métropole les mêmes opérations sont
-- rangées sous FEDER — cf. CLAUDE.md, dashboard/utils/periodes.
-- FUSIONS_ENVELOPPES_SANS_LIBELLE). La correction IEJ (contrepartie FSE
-- retranchée de l'enveloppe FSE, ajoutée à l'IEJ) est déjà faite en amont,
-- dans programme_totals_2014_2020.json (data-pipeline/programme_totals_2014_2020.py)
-- — rien à refaire ici.
CREATE VIEW v_enveloppes_2014_2020 AS
SELECT perimetre, fonds, SUM(montant_ue) AS programme
FROM (
    SELECT
        p.region AS perimetre,
        CASE
            WHEN p.fonds = 'FEDER REACT-EU'
             AND NOT EXISTS (
                 SELECT 1 FROM v_engage_2014_2020 e
                 WHERE e.perimetre = p.region AND e.fonds = 'FEDER REACT-EU'
             )
            THEN 'FEDER'
            ELSE p.fonds
        END AS fonds,
        p.montant_ue
    FROM programme_totals p
    WHERE p.periode = '2014-2020'
) y
GROUP BY perimetre, fonds;

-- Même formule que v_pilotage (03_pilotage.sql) : taux jamais plafonné,
-- reste à engager calculé PAR FONDS puis planché à 0 (#62). FEAD et
-- FEDER-FSE n'apparaissent jamais ici : aucune ligne programme_totals pour
-- ces deux libellés (le premier hors Fonds ESI, le second pas un fonds mais
-- le libellé du PNAT Europ'Act — cf. MENTION_FONDS_HORS_RAPPROCHEMENT).
CREATE VIEW v_pilotage_2014_2020 AS
SELECT
    ev.perimetre,
    ev.fonds,
    ev.programme,
    COALESCE(e.engage, 0) AS engage,
    CASE WHEN ev.programme > 0 THEN COALESCE(e.engage, 0) / ev.programme ELSE 0 END AS taux,
    GREATEST(ev.programme - COALESCE(e.engage, 0), 0) AS reste_a_engager
FROM v_enveloppes_2014_2020 ev
LEFT JOIN v_engage_2014_2020 e ON e.perimetre = ev.perimetre AND e.fonds = ev.fonds;

-- Catégories de cohésion UE 2014-2020 par région moderne (décision 2014/99,
-- data/processed/categories_ue_2014_2020.json), avec le plafond de
-- cofinancement déjà résolu en (min, max) — cf. load_data.py, qui appelle
-- directement dashboard/utils/cofinancement.plafond_intervalle_2014_2020
-- plutôt que de dupliquer la règle ici. Un intervalle, pas un nombre : six
-- régions modernes sur treize réunissent d'anciennes régions de catégories
-- différentes (voir la docstring Python).
CREATE TABLE categories_ue_2014_2020 (
    region TEXT PRIMARY KEY,
    categorie_ue TEXT,
    plafond_min NUMERIC,
    plafond_max NUMERIC
);

-- Taux de cofinancement par opération face au plafond de sa région (art. 120
-- §3, règlement 1303/2013). Trois fonds hors champ, exclus par construction
-- (cf. dashboard/utils/cofinancement.FONDS_HORS_PLAFOND, dupliqué ici en toute
-- lettres — même risque de divergence que le reste des vues SQL de ce
-- dossier, non testé automatiquement, cf. README) :
--   - FEDER REACT-EU (dérogation jusqu'à 100 %, règlement 2020/2221 art. 92 ter §12) ;
--   - IEJ (plafond RELEVÉ par l'art. 120 §3, pas plafonné) ;
--   - FEAD (hors Fonds ESI, transfert art. 94, règlement 223/2014).
-- `depasse_plafond` compare au plafond MAXIMUM de la fourchette plutôt qu'au
-- minimum : le plafond se fixe par axe prioritaire (pas par opération, le
-- fichier ne le porte pas) et peut être majoré de dix points (§5) — comparer
-- au minimum multiplierait les faux positifs sur les régions mixtes.
-- Part de `v_perimetre_2014_2020`, pas directement d'`operations` : sinon les
-- opérations Bretagne du vieux fichier europe.bzh (`2014-2020-bretagne`,
-- remplacé par `bretagne-officiel`, cf. en-tête de fichier) et les quelques
-- opérations marginales Synergie des trois régions à fichier propre
-- s'ajouteraient à celles déjà comptées par leur fichier substituant —
-- exactement le double-comptage que `v_perimetre_2014_2020` existe pour
-- éviter. `perimetre = 'national'` (Synergie hors-région, PON FSE/IEJ
-- national) n'a pas de ligne dans `categories_ue_2014_2020` : le JOIN les
-- écarte naturellement, un plafond de cofinancement n'ayant de sens que par
-- région.
CREATE VIEW v_cofinancement_2014_2020 AS
SELECT
    p.numero_operation, p.perimetre AS region, p.fonds,
    p.montant_ue, p.depenses_eligibles,
    CASE WHEN p.depenses_eligibles > 0 THEN p.montant_ue / p.depenses_eligibles END AS taux,
    c.categorie_ue, c.plafond_min, c.plafond_max,
    CASE
        WHEN p.depenses_eligibles > 0 AND c.plafond_max IS NOT NULL
         AND p.montant_ue / p.depenses_eligibles > c.plafond_max
        THEN TRUE ELSE FALSE
    END AS depasse_plafond
FROM v_perimetre_2014_2020 p
JOIN categories_ue_2014_2020 c ON c.region = p.perimetre
WHERE p.fonds NOT IN ('FEDER REACT-EU', 'IEJ', 'FEAD')
  AND p.montant_ue IS NOT NULL AND p.depenses_eligibles IS NOT NULL;

CREATE VIEW v_cofinancement_2014_2020_summary AS
SELECT
    region, fonds, categorie_ue, plafond_min, plafond_max,
    COUNT(*) AS n_operations,
    COUNT(*) FILTER (WHERE depasse_plafond) AS n_depassements,
    COALESCE(SUM(montant_ue) FILTER (WHERE depasse_plafond), 0) AS montant_depassements
FROM v_cofinancement_2014_2020
GROUP BY region, fonds, categorie_ue, plafond_min, plafond_max;
