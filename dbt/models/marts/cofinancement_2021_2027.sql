-- Port de `v_cofinancement_2021_2027` (05_vues_unifiees.sql).
--
-- Le plafond vient du seed `region_metadata`, résolu EN PYTHON par
-- `dbt/generer.py` (utils.cofinancement.plafond_categorie) : Auvergne-Rhône-Alpes
-- porte une catégorie mixte dont le plafond est une moyenne pondérée extraite du
-- libellé par expression régulière. Le transcrire en SQL en ferait une seconde
-- implémentation à maintenir — même arbitrage que load_data.py.
--
-- Tolérance 1e-6 sur la comparaison au plafond : même valeur que
-- `dashboard/utils/stats.TOLERANCE_RELATIVE_PLAFOND` (#126). De nombreuses
-- opérations sont programmées PILE au plafond, ce qui laisse un écart résiduel
-- de quelques 10⁻⁷ selon le sens de l'arrondi — un vrai dépassement, mais sous
-- le centime. Sans cette tolérance, cette table et l'écran Streamlit
-- classeraient différemment les mêmes opérations.
--
-- Le filtre `FONDS_HORS_PLAFOND` (FEDER REACT-EU, IEJ, FEAD) ne retire rien en
-- 2021-2027 — la période ne porte que FEDER, FSE+ et FTJ. Il est écrit quand
-- même, à l'identique de 2014-2020, pour que la règle soit la même des deux
-- côtés et non « celle qui se trouvait utile pour cette période ».
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
    r.categorie_ue,
    r.plafond_cofinancement AS plafond,
    CASE
        WHEN o.depenses_eligibles > 0 AND r.plafond_cofinancement IS NOT NULL
         AND o.montant_ue / o.depenses_eligibles > r.plafond_cofinancement * 1.000001
        THEN TRUE ELSE FALSE
    END AS depasse_plafond
FROM {{ ref('stg_operations_2021_2027') }} o
JOIN {{ ref('region_metadata') }} r ON r.region = o.region
WHERE NOT o.is_interregional AND NOT o.is_national
  AND o.fonds NOT IN ('FEDER REACT-EU', 'IEJ', 'FEAD')
  AND o.montant_ue IS NOT NULL AND o.depenses_eligibles IS NOT NULL
