-- Port de `v_repartition_all` (05_vues_unifiees.sql) : répartition thématique
-- par (période, périmètre, fonds, niveau1, niveau2).
--
-- Les deux périodes ne décrivent PAS la même chose, et ce n'est pas rattrapable :
-- 2021-2027 a une hiérarchie à deux étages (objectif stratégique → objectif
-- spécifique), 2014-2020 une dimension plate (domaine d'intervention, jamais
-- assimilée à un objectif stratégique). D'où `niveau1`/`niveau2` plutôt que des
-- noms de période, et `niveau2` NULL sur tout le côté 14-20 : l'union rend
-- l'asymétrie visible au lieu de la masquer sous un libellé commun.
--
-- COUVERTURE, très inégale et c'est le fait le plus important avant d'en tirer
-- un graphique : 16 619/16 625 opérations en 2021-2027, contre 6 269 opérations
-- et 1 991 M€ en 2014-2020 — 9,7 % des 20 494 M€ de la période. Le domaine
-- d'intervention n'est porté QUE par les trois fichiers régionaux ; Synergie et
-- le PON FSE, qui font les 90 % restants, ne le portent pas du tout.
--
-- La dimension absente devient 'Non renseigné' au lieu d'être filtrée : sans ça
-- un treemap 14-20 afficherait 1 991 M€ là où la période en vaut 20 494, sans
-- que rien à l'écran ne dise où sont passés les 90 % manquants. C'est aussi ce
-- qui rend le contrôle de complétude possible — regroupée par (période,
-- périmètre, fonds), cette table doit redonner `engage_all` ligne à ligne.
-- Le périmètre est une COLONNE sur la partition mono-région, une constante sur
-- les deux autres. Le troisième élément dit s'il peut entrer dans le GROUP BY :
-- PostgreSQL refuse `GROUP BY 'national'` (« non-integer constant in GROUP BY »),
-- là où DuckDB l'accepte. Un des rares écarts de dialecte rencontrés.
{% set partitions = [
    ("region", "NOT is_interregional AND NOT is_national AND region IS NOT NULL", true),
    ("'national'", "is_national", false),
    ("'interregional'", "is_interregional", false),
] %}

{% for perimetre, filtre, groupable in partitions %}
SELECT
    periode,
    {{ perimetre }} AS perimetre,
    fonds,
    COALESCE(objectif_strategique, 'Non renseigné') AS niveau1,
    COALESCE(objectif_specifique, 'Non renseigné') AS niveau2,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS engage
FROM {{ ref('stg_operations_2021_2027_conventionnees') }}
WHERE {{ filtre }} AND fonds IS NOT NULL
GROUP BY periode, {% if groupable %}{{ perimetre }}, {% endif %}fonds, 4, 5

UNION ALL
{% endfor %}

-- Côté 2014-2020 : part de `perimetre_2014_2020`, jamais des staging.
SELECT
    '2014-2020' AS periode,
    perimetre,
    fonds,
    COALESCE(domaine_intervention, 'Non renseigné') AS niveau1,
    CAST(NULL AS VARCHAR) AS niveau2,
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS engage
FROM {{ ref('perimetre_2014_2020') }}
WHERE fonds IS NOT NULL
GROUP BY perimetre, fonds, 4
