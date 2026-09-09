{# Les six vues de base répètent le même bloc d'agrégats (02_views.sql) : une
   macro plutôt que six copies. C'est le premier gain net de dbt sur du SQL nu —
   la formule d'un agrégat n'existe qu'une fois. #}
{% macro resume() %}
    COUNT(*) AS n_operations,
    SUM(montant_ue) AS montant_ue_total,
    AVG(montant_ue) AS montant_ue_moyen,
    SUM(depenses_eligibles) AS depenses_total,
    AVG(depenses_eligibles) AS depenses_moyen
{% endmacro %}
