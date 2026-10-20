{#
  Un schéma par couche sur la cible PostgreSQL (#231, ADR 002) : `staging`,
  `marts`, `reference`. Metabase ne lit que `marts`, le seul schéma ouvert à son
  lecteur (`metabase/provision_roles.py`) ; staging et seeds ne lui sont plus
  visibles, et le seed `region_metadata` ne peut plus masquer la table
  `public.region_metadata` homonyme.

  Sans cette macro, dbt préfixerait par le schéma de la cible
  (`staging_marts`). Sur DuckDB, la cible reste à plat, dans `main` :
  `verifier_equivalence.py`, `verifier_harmonisation.py` et Dagster lisent les
  modèles par leur nom seul, et le découpage ne sert qu'à Metabase.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.type == 'postgres' and custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
