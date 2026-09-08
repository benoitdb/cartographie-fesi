-- Port de `v_engage_all` (05_vues_unifiees.sql) : engagé par (période, périmètre, fonds).
--
-- LE PIÈGE CENTRAL DE LA VUE D'ORIGINE N'EXISTE PLUS ICI, et c'est un résultat
-- du portage. Le fichier d'origine devait écrire un `WHERE periode = '2021-2027'`
-- explicite sur son côté 21-27, parce que `v_pilotage` et
-- `v_engage_by_perimetre_fonds` produisent AUSSI des lignes 2014-2020 en sommant
-- aveuglément les six sources qui se chevauchent — unionner sans ce filtre
-- comptait la période deux fois (19 901 → 39 958 M€).
--
-- Ici, `engage_by_perimetre_fonds` part d'un staging PAR SOURCE qui ne contient
-- que 2021-2027 : le filtre n'est plus une condition de justesse à ne pas
-- oublier, il est structurel. Le modèle ne PEUT pas produire de ligne 14-20.
SELECT periode, perimetre, fonds,
       n_operations, engage
FROM {{ ref('engage_by_perimetre_fonds_detail') }}

UNION ALL

SELECT '2014-2020' AS periode, perimetre, fonds, n_operations, engage
FROM {{ ref('engage_2014_2020') }}
