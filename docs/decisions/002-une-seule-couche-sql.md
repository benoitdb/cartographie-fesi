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

## Amendement du 2026-10-20 — mise en œuvre, PR 1 de #231

- **Un schéma par couche sur PostgreSQL** : `marts` (lu par Metabase), `staging`
  (staging et intermediate), `reference` (seeds), par
  `dbt/macros/generate_schema_name.sql`. La cible DuckDB reste à plat dans
  `main` : ses lecteurs (`verifier_equivalence.py`, `verifier_harmonisation.py`,
  Dagster) désignent les modèles par leur seul nom. Le seed `region_metadata`
  ne peut plus masquer `public.region_metadata`.
- **Le lecteur Metabase** reçoit `USAGE` sur `marts` et des privilèges par défaut
  en lecture (`provision_roles.py`) : dbt recrée ses tables à chaque build.
- **Les marts ne reproduisent pas toutes les vues sur les deux périodes.** Huit
  marts ne couvrent que 2021-2027 (`by_region`, `national`, `interregional`,
  `by_fonds`, `by_region_fonds`, `by_objectif_strategique`, `pilotage`,
  `cofinancement_2021_2027`), là où leurs vues portaient les sept sources. C'est
  un choix de construction de #135, pas un arbitrage nommé ; la mention « 18 vues
  sur 19 identiques ligne à ligne » de `docs/spike-dbt-135.md` vaut sur
  2021-2027. Metabase n'est pas touché : il ne lit aucune de ces huit vues.
  **Option A retenue le 2026-10-20** : `verify_aggregates.py` ne vérifie plus
  que la source 2021-2027, et le test du double-comptage contrôle que
  `marts.pilotage` n'a aucune ligne 2014-2020. Ce que Metabase affiche sur
  2014-2020 reste vérifié par `verify_pilotage_2014_2020.py`,
  `verify_vues_unifiees.py` et `verify_dashboards.py`.

## Amendement du 2026-10-20 — PR 2 de #231, vues retirées

- `metabase/init/02` à `05` et `dbt/verifier_vues_postgres.py` sont supprimés.
  Les trois éléments qui n'étaient pas des vues passent dans `01_schema.sql` :
  les tables `categories_ue_2014_2020` et `allocations_rup`, et la colonne
  `region_metadata.plafond_cofinancement`.
- Base locale : les 19 vues ont été supprimées par un seul `DROP VIEW` sans
  `CASCADE`, sans recréer le volume. Les marts, les scripts de vérification et
  `verify_dashboards.py` (28 890 valeurs) restent verts sans elles.
- Les commentaires qui servaient de consigne (« à faire évoluer ensemble »)
  désignent désormais les marts ; le seuil de 0,01 du taux divergent et la
  tolérance de 1e-6 restent écrits en dur dans les marts `cofinancement_*`.

## Amendement du 2026-10-20 — étape 2, rattachement départemental (#232)

- Décidé : la cascade vit dans `data-pipeline/departements.py` ; `ingest.py`
  écrit `dept` et `dept_source` dans chaque Parquet ; deux PR. Seule
  importation du pipeline par le dashboard : `DEPT_SOURCES`.
- PR #240 : Streamlit lit les colonnes au lieu de recalculer ; résultat
  identique au calcul précédent sur les 72 675 opérations des six sources
  commitées.
- PR 2 : colonnes ajoutées à `operations` (`01_schema.sql`, `ALTER TABLE` sur la
  base locale sans recréer le volume), chargées par `load_data.py`, portées par
  le staging dbt des deux cibles (`generer.py`). Metabase voit la colonne ;
  aucune carte ne l'utilise encore.
- Le rattachement au périmètre 2014-2020 n'est pas matérialisé : il fera l'objet
  d'un spike borné avant toute décision.
