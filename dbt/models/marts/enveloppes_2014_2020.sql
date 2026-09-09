-- Port de `v_enveloppes_2014_2020` (04_periode_2014_2020.sql).
--
-- Règle : une enveloppe `FEDER REACT-EU` bascule sur `FEDER` quand le périmètre
-- ne porte AUCUNE opération étiquetée `FEDER REACT-EU`. Seuls les DROM
-- distinguent ce libellé dans Synergie ; en métropole les mêmes opérations sont
-- rangées sous FEDER, et garder les deux séparés afficherait un REACT-EU à 0 %
-- face à un FEDER gonflé d'autant.
--
-- La table de fusion vient de `periodes.FUSIONS_ENVELOPPES_SANS_LIBELLE` via
-- `dbt_project.yml` — elle n'est plus recopiée dans le SQL (#125).
--
-- La correction IEJ (contrepartie FSE retranchée de l'enveloppe FSE, ajoutée à
-- l'IEJ) est déjà faite en amont par `programme_totals_2014_2020.py`.
{% set fusions = var('fusions_enveloppes_sans_libelle') %}

SELECT perimetre, fonds, SUM(montant_ue) AS programme
FROM (
    SELECT
        p.region AS perimetre,
        CASE
        {%- for fonds_source, fonds_accueil in fusions.items() %}
            WHEN p.fonds = {{ litteral(fonds_source) }}
             AND NOT EXISTS (
                 SELECT 1 FROM {{ ref('engage_2014_2020') }} e
                 WHERE e.perimetre = p.region AND e.fonds = {{ litteral(fonds_source) }}
             )
            THEN {{ litteral(fonds_accueil) }}
        {%- endfor %}
            ELSE p.fonds
        END AS fonds,
        p.montant_ue
    FROM {{ ref('programme_totals') }} p
    WHERE p.periode = '2014-2020'
) y
GROUP BY perimetre, fonds
