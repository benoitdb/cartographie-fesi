{# Littéral SQL depuis une valeur Jinja, apostrophes échappées.

   `| tojson` ne convient PAS : il produit des guillemets doubles, qui sont des
   identifiants en SQL et non des chaînes — « Bretagne » y devient un nom de
   colonne. Le piège est silencieux à la compilation et n'apparaît qu'à
   l'exécution.

   L'échappement n'est pas théorique ici : « Provence-Alpes-Côte d'Azur » porte
   une apostrophe, et le jour où cette région rejoint une liste de règles, un
   `join` naïf casserait la requête. #}
{% macro litteral(valeur) %}{{ "'" ~ (valeur | string | replace("'", "''")) ~ "'" }}{% endmacro %}

{# Liste de littéraux séparés par des virgules, pour un `IN (...)`. #}
{% macro litteraux(valeurs) %}{% for v in valeurs %}{{ litteral(v) }}{% if not loop.last %}, {% endif %}{% endfor %}{% endmacro %}
