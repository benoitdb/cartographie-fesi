-- Port de `v_cofinancement_2014_2020_summary` (04_periode_2014_2020.sql).
SELECT
    region, fonds, categorie_ue, plafond_min, plafond_max,
    COUNT(*) AS n_operations,
    COUNT(*) FILTER (WHERE depasse_plafond) AS n_depassements,
    COALESCE(SUM(montant_ue) FILTER (WHERE depasse_plafond), 0) AS montant_depassements,
    COUNT(*) FILTER (WHERE taux_divergent) AS n_taux_divergents,
    COALESCE(SUM(montant_ue) FILTER (WHERE taux_divergent), 0) AS montant_taux_divergents
FROM {{ ref('cofinancement_2014_2020') }}
GROUP BY region, fonds, categorie_ue, plafond_min, plafond_max
