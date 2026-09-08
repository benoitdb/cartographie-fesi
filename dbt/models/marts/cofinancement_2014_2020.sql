-- Port de `v_cofinancement_2014_2020` (04_periode_2014_2020.sql).
-- Taux de cofinancement par opération face au plafond de sa région
-- (art. 120 §3, règlement 1303/2013).
--
-- Les trois fonds hors champ viennent de `cofinancement.FONDS_HORS_PLAFOND` via
-- `dbt_project.yml`, plus recopiés en toutes lettres (#125) : FEDER REACT-EU
-- (dérogation jusqu'à 100 %), IEJ (plafond RELEVÉ par l'art. 120 §3, pas
-- plafonné), FEAD (hors Fonds ESI).
--
-- `depasse_plafond` compare au plafond MAXIMUM de la fourchette, pas au minimum :
-- le plafond se fixe par axe prioritaire et peut être majoré de dix points (§5) —
-- comparer au minimum multiplierait les faux positifs sur les régions mixtes.
--
-- Part de `perimetre_2014_2020` et non des staging : sinon les opérations
-- Bretagne du vieux fichier et les quelques opérations Synergie marginales des
-- trois régions à fichier propre s'ajouteraient à celles déjà comptées.
-- `perimetre = 'national'` n'a pas de ligne dans `categories_ue_2014_2020` : le
-- JOIN l'écarte, un plafond de région n'ayant pas de sens hors d'une région.
--
-- `taux` fait foi partout ; `taux_declare` (porté par les seules Bretagne,
-- Normandie et Nouvelle-Aquitaine) est un signal de qualité de source, affiché à
-- part. Un écart de plus d'un point entre les deux mesures de la même opération
-- signale que la source mérite d'être regardée — ni un dépassement, ni une
-- erreur SQL.
--
-- Tolérance 1e-6, même valeur que `stats.TOLERANCE_RELATIVE_PLAFOND` (#126).
SELECT
    p.numero_operation, p.perimetre AS region, p.fonds,
    p.montant_ue, p.depenses_eligibles,
    CASE WHEN p.depenses_eligibles > 0 THEN p.montant_ue / p.depenses_eligibles END AS taux,
    p.taux_declare,
    CASE
        WHEN p.depenses_eligibles > 0 AND p.taux_declare IS NOT NULL
         AND ABS(p.montant_ue / p.depenses_eligibles - p.taux_declare) > 0.01
        THEN TRUE ELSE FALSE
    END AS taux_divergent,
    c.categorie_ue, c.plafond_min, c.plafond_max,
    CASE
        WHEN p.depenses_eligibles > 0 AND c.plafond_max IS NOT NULL
         AND p.montant_ue / p.depenses_eligibles > c.plafond_max * 1.000001
        THEN TRUE ELSE FALSE
    END AS depasse_plafond
FROM {{ ref('perimetre_2014_2020') }} p
JOIN {{ ref('categories_ue_2014_2020') }} c ON c.region = p.perimetre
WHERE p.fonds NOT IN ({{ litteraux(var('fonds_hors_plafond')) }})
  AND p.montant_ue IS NOT NULL AND p.depenses_eligibles IS NOT NULL
