-- Port de `v_cofinancement_all` (05_vues_unifiees.sql).
--
-- Agrégé et non par opération : les deux périodes portent des colonnes de
-- plafond différentes par nature (un intervalle en 2014-2020, un point en
-- 2021-2027), et forcer l'union au niveau opération obligerait à choisir
-- laquelle des deux formes perdre. Ici `plafond_min`/`plafond_max` valent le
-- même nombre côté 2021-2027, ce qui est exact plutôt que dégradé.
SELECT
    '2014-2020' AS periode,
    region, fonds, categorie_ue, plafond_min, plafond_max,
    n_operations, n_depassements, montant_depassements,
    n_taux_divergents, montant_taux_divergents
FROM {{ ref('cofinancement_2014_2020_summary') }}

UNION ALL

SELECT
    '2021-2027' AS periode,
    region, fonds, categorie_ue,
    plafond AS plafond_min, plafond AS plafond_max,
    COUNT(*) AS n_operations,
    COUNT(*) FILTER (WHERE depasse_plafond) AS n_depassements,
    COALESCE(SUM(montant_ue) FILTER (WHERE depasse_plafond), 0) AS montant_depassements,
    COUNT(*) FILTER (WHERE taux_divergent) AS n_taux_divergents,
    COALESCE(SUM(montant_ue) FILTER (WHERE taux_divergent), 0) AS montant_taux_divergents
FROM {{ ref('cofinancement_2021_2027') }}
GROUP BY region, fonds, categorie_ue, plafond
