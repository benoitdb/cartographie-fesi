# ADR 002 — Une seule couche SQL : Metabase lit les marts dbt

**Date :** 2026-10-19
**Statut :** accepté — issue #178 (cadrage), mise en œuvre #230, #231, #232

## Contexte

Streamlit et Metabase doivent afficher les mêmes montants, donc appliquer les
mêmes règles métier : rattacher une opération 2014-2020 à son périmètre,
détecter un dépassement du plafond de cofinancement, agréger l'engagé.

Au 19 octobre 2026, ces règles existent en trois copies :

| Copie | Où | Lue par |
|---|---|---|
| Python | `dashboard/utils/` | Streamlit |
| 19 vues SQL (672 lignes) | `metabase/init/02` à `05` | Metabase |
| 20 marts dbt (462 lignes) | `dbt/models/marts/` | aucun écran (contrôles, Dagster) |

Les marts ont été écrits pour remplacer les vues (#135), mais Metabase n'a
jamais basculé. Les deux copies SQL ne sont pas fabriquées pareil : pour dbt,
les tables de règles sont générées depuis Python (`dbt/generer.py`, contrôlé en
CI) ; dans les vues, elles sont recopiées à la main. Les deux copies SQL ne sont
comparées que par un script local (`dbt/verifier_vues_postgres.py`).

## Décision

1. **Metabase lit les marts dbt** construits dans PostgreSQL
   (`dbt build --target postgres`). Les vues `metabase/init/02` à `05` sont
   retirées ; `01_schema.sql` (les tables) reste. Le code dbt ne change pas : il
   est construit sur deux cibles, PostgreSQL pour Metabase, DuckDB pour le
   contrôle d'équivalence en CI. Mise en œuvre en deux PR (rebrancher, puis
   retirer) : #231, après #230.
2. **Les règles par opération que le SQL fait mal sont calculées en amont**, par
   le pipeline, et écrites dans les Parquet. D'abord le rattachement
   départemental (`dept`, `dept_source`, #232) ; le périmètre 14-20 seulement
   après un spike, car une opération appartient à plusieurs périmètres.
3. **Streamlit continue de calculer en pandas** (option B de #178, différée).

## Options écartées

- **Statu quo** : chaque règle reste à modifier trois fois, et l'accord entre
  les deux SQL n'est surveillé qu'à la main.
- **Garder les vues, abandonner dbt** : retire aussi une copie, mais perd les
  tables générées depuis Python, la cible DuckDB qui permet le contrôle en CI
  sans infrastructure, les tests dbt et le graphe Dagster.
- **Streamlit lit aussi les marts (option B)** : une seule copie en tout, mais
  Streamlit Community Cloud ne lance pas dbt (il faudrait committer les
  résultats), et les pages comme les tests Python seraient à réécrire. À rouvrir
  avec la suite de la trajectoire dbt/Dagster (#140, #186).

## Conséquences

- Une règle passe de trois copies à deux : Python et dbt. Côté SQL, il ne reste
  que la version dont les tables de règles sont générées.
- Le même SQL est vérifié deux fois : sur DuckDB contre les agrégats Python
  (`equivalence-dbt`), sur PostgreSQL par les scripts de `verify-metabase`.
- Le lancement local de Metabase suppose un `dbt build --target postgres`.
- `dbt/verifier_vues_postgres.py` devient sans objet une fois les vues retirées.

## Limites connues

- **Python et SQL restent deux copies.** Leur accord est surveillé en CI et, en
  local, par `verify_dashboards.py` (28 890 valeurs concordantes au 19 octobre
  2026).
- **La tolérance du plafond (1e-6)** est encore écrite en dur dans le SQL, alignée
  sur `utils/stats.TOLERANCE_RELATIVE_PLAFOND` par un commentaire.
- **Base locale** : les vues créées à l'initialisation du volume
  `metabase_pgdata` y restent après la suppression des fichiers ; elles se
  retirent par `DROP VIEW`, sans recréer le volume.
