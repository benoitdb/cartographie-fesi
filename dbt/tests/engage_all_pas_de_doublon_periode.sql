-- engage_all unionne les deux périodes : un même couple (périmètre, fonds) ne
-- doit apparaître qu'une fois par période. Un doublon signalerait une union mal
-- filtrée — le piège du double-comptage que le WHERE periode = '2021-2027'
-- évitait dans la vue SQL d'origine (05_vues_unifiees.sql).
SELECT periode, perimetre, fonds, COUNT(*) AS nb
FROM {{ ref('engage_all') }}
GROUP BY periode, perimetre, fonds
HAVING COUNT(*) > 1
