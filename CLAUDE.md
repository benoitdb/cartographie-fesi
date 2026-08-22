# Cartographie FESI — fonds européens structurels et d'investissement

## Pourquoi

Dashboard d'exploration et de pilotage des opérations conventionnées FEDER /
FSE+ / FTJ sur la programmation 2021-2027 : où va l'argent, à qui, à quel
rythme de consommation. Portfolio / démo, pas un outil de production.

## État actuel

Dashboard Streamlit multipage fonctionnel (Accueil + Vue Régionale + Volet
National + Comparateur), alimenté par un pipeline Python qui transforme le
fichier XLSX source en JSON.

**`main` est la référence** depuis la fusion de `streamlit-dashboard`
(PR #49, 2026-08-20) : elle porte le dashboard, ce fichier et les tests. Partir
de `main` et travailler sur une branche dédiée (`feat/...`, `fix/...`,
`test/...`), fusionnée par PR une fois la CI verte — pas de commit direct sur
`main` pour du code (les corrections de doc peuvent y aller directement).

`frontend/` est un **prototype React/Vite abandonné** au profit de Streamlit —
mais **il n'est pas mort** : le dashboard lit ses fichiers géographiques
(`frontend/public/geo/`). Ne pas supprimer ce dossier, et voir
`frontend/public/geo/SOURCES.md` pour la provenance de chaque contour.

## Commandes

Trois environnements, chacun avec son `requirements.txt` : `dashboard/venv/`
pour l'application, le pipeline (pandas, openpyxl, rapidfuzz), et `venv/` à la
racine pour les tests (`requirements-dev.txt`).

- **Lancer le dashboard** (depuis `dashboard/`, les imports `utils.*` en
  dépendent) :
  ```
  cd dashboard && venv/bin/streamlit run Accueil.py --server.port 8501
  ```
  (8502 est occupé par le projet Assistant RAG UE)
- **Régénérer les données** — depuis `data-pipeline/`, `ingest.py` d'abord car
  les autres scripts en dépendent :
  ```
  python ingest.py                        # XLSX -> data.json + operations.json
  python beneficiaires_fuzzy.py           # lit data.json, écrit beneficiaires_fuzzy.json
  python programme_totals.py              # Tableau 9B  -> programme_totals.json + programme_detail.json
  python dotations_os_totals.py           # Tableau 8   -> dotations_os.json
  python interreg_totals.py               # Tableau 10  -> interreg.json
  python transferts_solidarite_totals.py  # Tableau 3A/3B -> transferts_solidarite.json
  ```
- **`region_metadata.py`** est un script **one-shot** qui appelle Wikidata par
  le réseau. Ne pas le lancer dans une régénération de routine : son résultat
  est committé exprès pour que le dashboard tourne sans dépendance externe.
  À relancer une fois par an environ.

- **Tests** : `venv/bin/python -m pytest -q` (95 tests, ~7 s). Ils tournent sur
  un clone nu et en CI : aucun ne lit le XLSX ni les JSON générés. Ceux du
  pipeline éprouvent la logique sur des cas construits ; ceux du dashboard
  lisent la fixture committée dans `tests/fixtures/` (voir son README —
  **à régénérer quand le schéma de `data.json` change**).
  Environnement de test à la racine : `requirements-dev.txt`, qui tire
  maintenant *aussi* `dashboard/requirements.txt` (streamlit est nécessaire aux
  tests de fumée).
- **Lint** : `ruff check .` (config dans `pyproject.toml`), lancé en CI sur
  chaque PR. **`ruff format` n'est volontairement pas activé** : reformater 29
  fichiers sur 38 (~3 300 lignes) sur une couche dashboard sans tests produirait
  un diff que rien ne valide. À reconsidérer quand les tests couvriront le
  dashboard.
  La ligne de base transitoire (issues #50 à #54) est **soldée** depuis la
  PR #59 : `ignore` ne contient plus que `RUF001/002/003`, qui concernent les
  apostrophes typographiques et espaces insécables du français et sont
  permanentes. **Ne pas ajouter d'`ignore` sans ouvrir l'issue qui va avec** —
  et la retirer fait partie de la correction.

## Quoi (repo map)

- `dashboard/` — application Streamlit. `Accueil.py` = point d'entrée,
  `pages/` = pages multipage, `utils/` = toute la logique (chargement, calculs,
  styles, thèmes)
- `data-pipeline/` — scripts de transformation, un par sortie JSON
- `data-pipeline/reference/` — **données réglementaires saisies à la main**
  depuis l'Accord de partenariat 2021-2027 (tableaux 3A/3B, 8, 9B, 10), NUTS,
  catégories de cohésion UE. C'est la source de vérité des montants *programmés*,
  par opposition aux montants *engagés* qui viennent du XLSX.
- `data/raw/` — le XLSX source, **non versionné**
- `data/processed/` — JSON générés ; seuls ceux qui ne dépendent ni du réseau
  ni du XLSX sont committés (voir les commentaires du `.gitignore`, qui
  expliquent le choix fichier par fichier)
- `docs/sources/` — notes de travail sur les documents de référence, non versionné

## Pièges non devinables

- **Un clone frais ne tourne pas.** `data/raw/*.xlsx` et les JSON qui en
  dérivent (`data.json`, `operations.json`, `beneficiaires_fuzzy.json`) sont
  gitignorés. Il faut récupérer le XLSX source et relancer le pipeline.
- **Source du XLSX** :
  [europe-en-france.gouv.fr — liste des opérations FEDER/FSE+/FTJ 2021-2027](https://www.europe-en-france.gouv.fr/fr/ressources/liste-operations-feder-fse-ftj-2021-2027).
  Version utilisée : `20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx`.
- **Le fichier est republié 5 fois par an, en « annule et remplace »** — nouveau
  nom de fichier daté à chaque fois. `ingest.py` retient désormais le millésime
  le plus récent de `data/raw/` et **affiche lequel** au démarrage
  (`schema_source.trouver_fichier_source`, issue #47) : lire cette ligne avant
  toute conclusion sur des chiffres. Déposer le nouvel export suffit, mais
  l'ancien reste présent tant qu'on ne le supprime pas.
- **`ingest.py` mappe les colonnes par index, pas par nom** (choix assumé, jugé
  plus fiable que des libellés instables). Ce mapping est **vérifié** contre les
  libellés attendus au démarrage (`schema_source.build_cols`, issue #45) : un
  réordonnancement de la source fait échouer le pipeline avec un message qui
  nomme la position fautive, au lieu de produire des données fausses en silence.
  La comparaison ignore casse, espaces et type d'apostrophe — le fichier source
  mélange déjà `'` et `’`. Si la source change légitimement, mettre à jour
  `COLONNES_ATTENDUES` après avoir vérifié à quoi correspond chaque colonne.
- **Programmé ≠ engagé.** Les montants programmés viennent de l'Accord de
  partenariat dans sa version **préliminaire** de juin 2022, probablement
  révisée depuis. Tout taux de consommation est une estimation : la réserve
  méthodologique (`utils.pilotage.RESERVE_METHODO`) doit rester affichée à
  côté, ne jamais la retirer pour gagner de la place.
- **L'allocation Ultrapériphérique (RUP)** est comptée dans le total de la
  catégorie de base des DROM, car les opérations engagées ne disent pas de
  quelle enveloppe elles proviennent. Le détail RUP seul est exposé à part.

## Comment travailler ici

**Langue** : français dans le code (docs, commentaires, noms de variables
métier) comme dans les échanges.

**Terminologie** : **DROM-COM**, jamais « DOM-TOM » (terminologie officielle
depuis 2003) — dans le code, l'interface et les issues.

**Ton sur les écarts et valeurs atypiques** : le vocabulaire visible par
l'utilisateur reste neutre et descriptif — « Analyses & contrôle », « valeurs
atypiques », « écart ». Jamais « fraude », « inspecteur », ni un cadrage qui
suggère une accusation. Un écart de cofinancement est un point à expliquer, pas
un délit. (Les identifiants internes type `render_region_audit` sont
historiques et sans importance : c'est le texte affiché qui compte.)

**Cohérence visuelle** : les couleurs par fonds et par objectif stratégique
sont centralisées dans `utils/themes.py` (`FONDS_COLORS`,
`OBJECTIF_STRATEGIQUE_COLORS`). Toujours les réutiliser, ne jamais laisser
Plotly choisir ses couleurs par défaut — un même fonds doit avoir la même
couleur sur toutes les pages.

**Vérification** : le pipeline a des tests (harmonisation des régions,
rapprochement des bénéficiaires, schéma du fichier source) — les lancer et les
étendre.

Le dashboard a des **tests de fumée** (`tests/test_dashboard_pages.py`) : ils
rendent les 4 pages en headless via `streamlit.testing.v1.AppTest` et
n'attrapent que l'exception — import cassé, colonne renommée, fichier manquant.
**Ils ne disent rien de la justesse des chiffres ni de l'allure des pages.**
Toute modification touchant un calcul ou un affichage se vérifie donc toujours
en lançant réellement l'application et en regardant le résultat. Ne pas
annoncer qu'un changement fonctionne parce que la suite est verte.

Sur un changement touchant le pipeline, la vérification qui compte est de
**régénérer `data.json` et de le comparer au bit près** à une copie prise avant
modification (`aggregates` et `operations`) : les tests ne couvrent pas les
agrégats.

**GitHub issues — AI-driven dev, pas du vibe-coding** : toute limitation
connue, gotcha, piste d'évolution ou choix technique non trivial pris de façon
autonome est loggé comme issue sur `benoitdb/cartographie-fesi`, par défaut,
sans attendre qu'on le demande. Objectif : que l'utilisateur reste le décideur
capable d'expliquer et de ré-arbitrer un choix plus tard. Les issues servent
aussi de backlog de pistes explorées et bloquées (source manquante, donnée
absente) — les documenter comme telles plutôt que de les abandonner en silence.

**Couverture de test, état** : le pipeline est couvert sur ses points de
rupture silencieuse (schéma du fichier source, harmonisation des régions,
rapprochement des bénéficiaires) — **sauf le calcul d'agrégats**, écrit à plat
dans `ingest.py` et donc non testable en l'état
([issue #60](https://github.com/benoitdb/cartographie-fesi/issues/60)).

**La couche de calcul est couverte** depuis la PR #63 :
`tests/test_stats_calculs.py`, `tests/test_cofinancement_regles.py`,
`tests/test_pilotage_calculs.py` (58 tests sur des cas construits, valeurs
attendues posées à la main). Priorité y est donnée aux invariants documentés et
aux régressions déjà constatées : bornes IQR par fonds, montant manquant devenu
`NaN`, reste à engager calculé par fonds, dépassement d'enveloppe jamais
tronqué. **Chaque test a été vu échouer** sur une mutation du code qu'il
protège, avant d'être livré — un test vert qui ne peut pas rougir ne protège
rien.

Un calcul est encore enfoui dans un rendu (`render_kpi_pilotage`) et n'est donc
testable qu'indirectement, en relisant le texte affiché via `AppTest`
([issue #62](https://github.com/benoitdb/cartographie-fesi/issues/62)).

Restent hors couverture, sciemment : la mise en forme des figures (couleurs,
libellés, survols) hors des cas où elle porte un calcul, et les fonctions de
`stats.py` purement graphiques (histogramme, boîte à moustaches, nuages,
Pareto, Lorenz) — leur justesse se voit à l'écran, pas dans une assertion.
