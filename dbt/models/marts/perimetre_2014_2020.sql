-- SONDE (issue #135, étape 6). Port de `v_perimetre_2014_2020`
-- (metabase/init/04_periode_2014_2020.sql) — la vue qui porte les DEUX règles
-- les plus coûteuses du projet, et donc celle qui dit si la période 2014-2020
-- est migrable à un coût raisonnable :
--
--   SUBSTITUTION — Bretagne, Normandie et Nouvelle-Aquitaine ont leur propre
--   fichier et REMPLACENT Synergie sur leur région (#95) ;
--   ADDITION — le PON FSE est routé par PROGRAMME et non par la région portée
--   sur chaque ligne : les cinq PO FSE État des DROM rejoignent leur région,
--   PON FSE et PO IEJ national rejoignent le volet national.
--
-- Ce qui change par rapport à la vue d'origine, et c'est tout l'intérêt de la
-- sonde : les deux règles ne sont plus écrites en dur dans le SQL. La liste des
-- régions substituées et la table de routage du PON FSE viennent de variables
-- de projet (`dbt_project.yml`), elles-mêmes alimentables depuis le Python qui
-- en est la source de vérité (`periodes.REGIONS_PON_FSE_2014_2020` et le
-- `if/elif` de la page 5). C'est la réponse concrète à l'issue #125 : la règle
-- cesse d'exister en double.
--
-- Le vieux fichier Bretagne (`2014-2020-bretagne`, europe.bzh) n'y figure
-- jamais : remplacé par `bretagne-officiel` pour tout usage autre que la page
-- « Validation de la source ».

{% set regions_substituees = var('regions_substituees_2014_2020') %}
{% set routage_pon_fse = var('routage_pon_fse_2014_2020') %}

-- Synergie : périmètre régional, sauf les trois régions à fichier propre.
SELECT numero_operation, fonds, montant_ue, depenses_eligibles,
       taux_cofinancement AS taux_declare, region AS perimetre, domaine_intervention
FROM {{ ref('stg_operations_2014_2020_synergie') }}
WHERE NOT is_interregional AND NOT is_national
  AND region IS NOT NULL
  AND region NOT IN ({{ litteraux(regions_substituees) }})

UNION ALL

-- Synergie : volet national, inchangé.
SELECT numero_operation, fonds, montant_ue, depenses_eligibles,
       taux_cofinancement AS taux_declare, 'national' AS perimetre, domaine_intervention
FROM {{ ref('stg_operations_2014_2020_synergie') }}
WHERE is_national

{% for source_id in ['2014_2020_normandie', '2014_2020_nouvelle_aquitaine', '2014_2020_bretagne_officiel'] %}
UNION ALL

-- Fichier régional hors-Synergie : chaque ligne est de cette région par
-- construction (prétraitement du pipeline), pas de filtre supplémentaire.
SELECT numero_operation, fonds, montant_ue, depenses_eligibles,
       taux_cofinancement AS taux_declare, region AS perimetre, domaine_intervention
FROM {{ ref('stg_operations_' ~ source_id) }}
WHERE region IS NOT NULL
{% endfor %}

UNION ALL

-- PON FSE : additif, routé par PROGRAMME. Le CASE est déplié depuis la table de
-- routage, il n'est plus recopié à la main.
SELECT numero_operation, fonds, montant_ue, depenses_eligibles,
       taux_cofinancement AS taux_declare,
       CASE libelle_programme
       {%- for programme, perimetre in routage_pon_fse.items() %}
           WHEN {{ litteral(programme) }} THEN {{ litteral(perimetre) }}
       {%- endfor %}
           ELSE 'national'
       END AS perimetre,
       domaine_intervention
FROM {{ ref('stg_operations_2014_2020_pon_fse') }}
