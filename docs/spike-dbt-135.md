# Spike dbt — rapport et recommandation

Issue [#135](https://github.com/benoitdb/cartographie-fesi/issues/135). Branche
`spike/dbt-135`, partie de `main`. Réalisé le 2026-09-08.

**Recommandation : lancer le chantier, en le limitant aux marts.** Le coût réel
est nettement inférieur à l'hypothèse haute de l'issue, et le cas réputé le plus
dur s'est révélé le plus rentable. Détail et réserves plus bas.

> **Suite donnée (2026-09-08, même journée).** La recommandation ayant été
> validée, les **19 vues** sont désormais portées, pas seulement les 10 du
> spike. Voir « Chantier réalisé » en fin de document.

## Ce qui a été construit

| | |
|---|---|
| Modèles de staging | 6 (une par source, générés) |
| Marts | 10 |
| Cibles | `dbt-duckdb` **et** `dbt-postgres`, mêmes modèles |
| Seeds | 2 (`programme_totals`, `region_metadata`) |
| Python du spike | 485 lignes (`generer.py` 267, `verifier_equivalence.py` 218) |

Marts portés : les six vues de base de `02_views.sql`, `engage_by_perimetre_fonds`
et `pilotage` (`03_pilotage.sql`), `cofinancement_2021_2027` (`05_vues_unifiees.sql`),
et `perimetre_2014_2020` (`04_periode_2014_2020.sql`, la sonde).

## Fidélité — le seul critère qui vaille

Trois recoupements, tous au vert :

| Oracle | Portée | Résultat |
|---|---|---|
| `agregats.calculer_agregats` rejoué sur le Parquet | 6 marts de base, 2021-2027 | **241 contrôles**, comptages exacts, montants au centime |
| Les 19 vues de la stack Metabase | 8 marts, 2021-2027 | **0 divergence**, ligne à ligne |
| `v_perimetre_2014_2020` | la sonde | **0 divergence** — 55 904 opérations, 20 631,179 M€, sur les **deux** moteurs |

## Les mesures fixées avant de coder

**1. Lignes écrites vs remplacées.** 115 lignes de code SQL dans les marts, pour
~164 lignes des vues correspondantes de `metabase/init/` — et ces 115 lignes
valent pour les deux moteurs, là où les vues n'existent que côté PostgreSQL.
S'y ajoute la suppression des jumeaux Python (`agregats.calculer_agregats`, les
formules de `pilotage.py`) que #125 signale comme divergence possible.

**2. Règles non exprimables en SQL — le vrai facteur de coût.** Deux, et elles
restent volontairement en Python, appelées par le codegen :

- `schema_source.normalise_libelle` (#45). Le fichier source mélange les
  apostrophes (U+0027 dans « Région de l'opération », U+2019 dans « Code postal
  de l'opération »). Du SQL qui cite les libellés au caractère près ne peut pas
  reproduire ce garde-fou.
- `cofinancement.plafond_categorie`. Moyenne pondérée extraite d'un libellé par
  expression régulière pour les catégories mixtes, plus la dérogation
  ultrapériphérique.

**3. Taux de fork DuckDB/PostgreSQL.** **0 / 10 marts** portent un conditionnel
de cible. Le fork est entièrement dans les 6 modèles de staging — et il est
généré, donc son coût de maintenance est celui d'un script, pas de six fichiers.

**4. Empreinte.** `dbt build` complet : 1,12 s de modèles, 7,3 s de mur,
**227 Mo de RSS crête**. Sans commune mesure avec les 1 Go de Streamlit Cloud —
et la question ne se pose de toute façon pas (voir plus bas).

**5. Artefact matérialisé.** Base DuckDB de **7,8 Mo** pour 23 Mo de Parquet
sources. Aucune régression sur les 246 Mo gagnés par #132.

## Ce que le spike a trouvé en chemin

**Un écart préexistant, désormais tracé en [#137](https://github.com/benoitdb/cartographie-fesi/issues/137).**
`ingest.py` calcule les agrégats sur le DataFrame non arrondi et écrit un Parquet
arrondi : 0,37 € d'écart entre ce qu'affiche Streamlit et ce que charge Metabase.
Sans rapport avec dbt, mais c'est dbt qui l'a rendu visible — et il a fallu deux
oracles au lieu d'un pour en tenir compte.

**Une erreur silencieuse, la mienne, et ce qu'elle démontre.** Le seed des
plafonds appelait `plafond_categorie(categorie)` sans le drapeau
`ultraperipherique` : la Martinique tombait à 60 % au lieu de 85 % (art. 349
TFUE), et 28 opérations passaient en dépassement de plafond à tort. Aucune
exception, aucun total déplacé — un seul booléen métier bascule. Ni `dbt test`
ni l'oracle DuckDB ne pouvaient l'attraper. C'est l'oracle PostgreSQL, les vues
existantes, qui l'a signalée. **Si le chantier est lancé, le harnais
d'équivalence n'est pas optionnel.**

**Trois pièges de dialecte, tous silencieux :** `| tojson` produit des
identifiants SQL et non des littéraux ; l'inférence de type des seeds donne
INTEGER (débordement à 4,6 Md€) puis DOUBLE là où PostgreSQL veut NUMERIC ; les
six sources n'ayant pas les mêmes colonnes, tout `UNION ALL` exige un contrat de
colonnes explicite, que la table large de PostgreSQL offrait gratuitement.

## Le risque « Streamlit Cloud » de l'issue n'existe pas

L'issue redoutait dbt dans un runtime à 1 Go. Or les données sont régénérées
**localement**, committées, et Streamlit Cloud ne fait que redéployer sur push
(cf. `CLAUDE.md`) — l'app ne lance jamais `ingest.py`. dbt tourne sur le poste ou
en CI. `requirements-dbt.txt` est séparé de `dashboard/requirements.txt` ; rien
ne part sur Cloud.

## La réserve qui reste, et elle est réelle

**L'harmonisation des régions n'a pas été éprouvée.** `region_mapping.py`
(377 lignes : table programme → région, `harmonize_region`, les drapeaux
interrégional/national) s'exécute **en amont** du Parquet. Le spike a donc démarré
après elle, et ne dit rien de son coût de migration. C'est la principale inconnue
restante — et la raison de borner le chantier aux marts.

Deux autres limites assumées : le spike n'a porté que 10 des 19 vues (les 9
autres se construisent sur celles-ci), et l'extraction (`sources.py`, 651 lignes,
six fonctions de prétraitement) est hors périmètre dbt par nature.

## Recommandation

**Lancer, avec ce périmètre :**

1. **dbt sur la couche marts**, les 9 vues restantes — elles s'appuient toutes
   sur ce qui est fait, dont la plus dure.
2. **Extraction et harmonisation restent en Python.** Ne pas tenter de porter
   `region_mapping.py` : coût inconnu, bénéfice faible, c'est de la logique de
   rapprochement, pas de la transformation ensembliste.
3. **Le codegen (`generer.py`) fait partie du livrable**, pas un échafaudage :
   c'est lui qui empêche la quatrième copie du renommage.
4. **Le harnais d'équivalence tourne en CI**, sur la cible DuckDB — pas besoin de
   PostgreSQL, donc pas l'obstacle qui bloque #125 aujourd'hui.
5. **DuckDB devient la cible de matérialisation côté Streamlit** — il arrive
   comme sous-produit, sans justification ad hoc. Ça clôt le point 2 de #133.

**Estimation révisée : 2 à 3 jours**, contre « deux jours comme deux semaines »
dans l'issue. Le socle est fait, le cas dur est fait et exact, et le fork entre
moteurs est nul sur la couche qui compte.


---

# Chantier réalisé

Les 9 vues restantes ont été portées dans la foulée, la recommandation ayant été
validée. **Le chantier est complet sur la couche marts.**

| | Spike | Après chantier |
|---|---|---|
| Marts | 10 | **20** (19 vues + 1 modèle intermédiaire) |
| Staging | 6 | 6 |
| Nœuds dbt | 18 | **29** |
| Lignes de code SQL (marts) | 115 | 255 |
| Fork de cible dans les marts | 0 | **0** |

Ajoutés : la période 2014-2020 complète (`engage_2014_2020`,
`enveloppes_2014_2020`, `pilotage_2014_2020`, `cofinancement_2014_2020` et son
résumé) et les quatre vues unifiées (`engage_all`, `pilotage_all`,
`repartition_all`, `cofinancement_all`).

## Fidélité : 18 vues sur 19 identiques ligne à ligne

La dix-neuvième diverge **exprès**, et dans le bon sens :
`engage_by_perimetre_fonds` porte les trois partitions d'`agregats.py` là où la
vue d'origine n'en porte que deux. Le modèle dbt retombe sur `v_by_fonds` au
centime (7 879 820 894,76 €) ; la vue existante s'arrête 1,625 M€ plus bas
(13 opérations interrégionales). C'est le bug que #129 avait corrigé dans
`v_engage_all` sans le reporter — [#138](https://github.com/benoitdb/cartographie-fesi/issues/138).

## Les règles métier ne sont plus recopiées

`generer.py` écrit un bloc de variables dans `dbt_project.yml` depuis leur source
de vérité Python : routage du PON FSE, fonds hors plafond, fusion des enveloppes
sans libellé. Le SQL les déplie par Jinja. **C'est la réponse complète à #125** —
à une exception près, documentée dans le codegen : la liste des trois régions
substituées vit dans un dictionnaire de `pages/5_Période_2014-2020.py`, donc
dans un module Streamlit non importable. La remonter dans `utils/periodes.py`
est un déplacement de trois lignes, à faire côté dashboard.

## Deux résultats structurels

**Le piège central de `05_vues_unifiees.sql` disparaît par construction.** La vue
d'origine devait écrire un `WHERE periode = '2021-2027'` explicite, faute de quoi
la période 2014-2020 était comptée deux fois (19 901 → 39 958 M€). Les staging
étant par **source**, un modèle 21-27 ne peut plus produire de ligne 14-20 : le
filtre cesse d'être une condition de justesse qu'on peut oublier.

**Le Parquet n'est pas un contrat typé.** « Union co-financing rate (%) » de
Nouvelle-Aquitaine est une chaîne (`'0.4'`, `'0.150000078336386'`) là où
Normandie et Bretagne publient des flottants. PostgreSQL ne le voit jamais,
`load_data.parse_numeric` normalisant en amont. La branche DuckDB a donc besoin
d'un `TRY_CAST` explicite sur les colonnes numériques et de date — équivalent
exact de `parse_numeric`/`parse_date`, qui renvoient `None` sur échec.

Écart de dialecte supplémentaire : `GROUP BY 'national'` est refusé par
PostgreSQL (« non-integer constant in GROUP BY ») et accepté par DuckDB.

## Empreinte finale

`dbt build` complet, 29 nœuds : **8,0 s de mur, 236 Mo de RSS crête**, base
DuckDB de 16 Mo. Aucune régression sur les 246 Mo gagnés par #132.

## Les quatre points arbitrés (2026-09-08)

**1. La dernière règle recopiée — remontée dans `utils/periodes.py`.** ✅ Fait.
`SOURCE_HORS_SYNERGIE` vivait dans `pages/5_Période_2014-2020.py`, un module
Streamlit qu'un script ne peut pas importer. Elle devient
`periodes.REGIONS_SUBSTITUEES_2014_2020`, épinglée par trois tests
([PR #139](https://github.com/benoitdb/cartographie-fesi/pull/139)). `generer.py`
l'importe : **les quatre règles métier de la période viennent désormais toutes de
leur source Python, aucune recopie.**

**2. Le harnais en CI — sur les 6 marts de base.** ✅ Fait. Job `equivalence-dbt`,
séparé des tests. Ce qui le rend possible là où `metabase/verify_*.py` ne l'est
pas (#125) : la cible DuckDB ne demande aucune infrastructure, et les Parquet
sont committés depuis #119/#132 — le clone nu a tout.

Le job fait plus que rejouer le harnais : il **régénère** staging, seeds et
règles, puis exige `git diff --exit-code` sur `dbt/`. Modifier une règle Python
sans relancer le codegen fait rougir la CI, **sans base de données**. C'est la
piste 1 de #125, obtenue comme effet de bord du codegen.

Couverture assumée : les 14 autres marts n'ont pas d'oracle Python — leur vérité
est la vue SQL, absente du clone nu — et les couvrir supposerait de figer des
valeurs de référence ou de réimplémenter la règle côté test, ce qui recréerait la
duplication qu'on vient de supprimer.

**3. Les vues `metabase/init/` — période de recouvrement.** ✅ Fait. Les vues
restent la vérité pour Metabase, dbt écrit dans son schéma, et
`dbt/verifier_vues_postgres.py` vérifie à chaque régénération que les deux disent
la même chose — **19 comparaisons, toutes au vert**. Les vues ne seront
supprimées qu'une fois ce filet resté vert sur plusieurs millésimes.

La dix-neuvième comparaison est un contrôle d'**écart** et non d'égalité : elle
vérifie que la divergence de `engage_by_perimetre_fonds` est exactement
l'interrégional FEDER et FSE+ ([#138](https://github.com/benoitdb/cartographie-fesi/issues/138)),
ni plus ni autre chose. Elle redeviendra un contrôle d'égalité quand #138 sera
corrigée.

**4. `region_mapping.py` — second spike dédié.**
[Issue #140](https://github.com/benoitdb/cartographie-fesi/issues/140) ouverte,
une demi-journée, même méthode que celui-ci. Point à poser avant de coder :
contrairement aux marts, **l'harmonisation n'est pas dupliquée aujourd'hui** —
le portage ne supprimerait donc aucune duplication, et le bénéfice serait la
couverture, pas la déduplication.
