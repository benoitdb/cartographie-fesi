# Cartographie FESI — fonds européens structurels et d'investissement

## Pourquoi

Dashboard d'exploration et de pilotage des opérations conventionnées FEDER /
FSE+ / FTJ sur la programmation 2021-2027 : où va l'argent, à qui, à quel
rythme de consommation. Portfolio / démo, pas un outil de production.

## État actuel

Dashboard Streamlit multipage fonctionnel (Accueil + Vue Régionale + Volet
National + Comparateur), alimenté par un pipeline Python qui transforme le
fichier XLSX source en JSON.

**Le travail se fait sur la branche `streamlit-dashboard`**, en avance de
4 commits sur `main`. Ne pas repartir de `main` sans le signaler.

`frontend/` est un **prototype React/Vite abandonné** au profit de Streamlit —
mais **il n'est pas mort** : le dashboard lit ses fichiers géographiques
(`frontend/public/geo/`). Ne pas supprimer ce dossier, et voir
`frontend/public/geo/SOURCES.md` pour la provenance de chaque contour.

## Commandes

Deux environnements distincts, avec leurs propres `requirements.txt` :
`dashboard/venv/` et le pipeline (pandas, openpyxl, rapidfuzz).

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

Pas de suite de tests à ce jour — c'est le manque connu du projet (voir plus bas).

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
  nom de fichier daté à chaque fois. Or `XLSX_PATH` est **codé en dur** dans
  `ingest.py` : une mise à jour de la source exige d'éditer ce chemin, sinon le
  pipeline continue de régénérer les données à partir de l'ancien millésime.
  Vérifier la date du fichier avant toute conclusion sur des chiffres.
- **`ingest.py` mappe les colonnes par index, pas par nom** (choix assumé,
  jugé plus fiable). Un changement d'ordre des colonnes dans le fichier source
  passera donc totalement inaperçu et produira des données fausses sans erreur.
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

**Vérification** : le dashboard n'a pas de tests, donc toute modification
touchant un calcul (agrégats, taux, rapprochements) se vérifie en lançant
réellement l'application et en regardant le résultat, pas en supposant. Ne pas
annoncer qu'un changement fonctionne sans l'avoir affiché.

**GitHub issues — AI-driven dev, pas du vibe-coding** : toute limitation
connue, gotcha, piste d'évolution ou choix technique non trivial pris de façon
autonome est loggé comme issue sur `benoitdb/cartographie-fesi`, par défaut,
sans attendre qu'on le demande. Objectif : que l'utilisateur reste le décideur
capable d'expliquer et de ré-arbitrer un choix plus tard. Les issues servent
aussi de backlog de pistes explorées et bloquées (source manquante, donnée
absente) — les documenter comme telles plutôt que de les abandonner en silence.

**Manque connu, assumé** : aucun test automatisé sur ~5 200 lignes de Python.
Le risque principal est une régression silencieuse dans les agrégats du
pipeline ou le rapprochement des bénéficiaires. Priorité quand des tests seront
ajoutés : les totaux du pipeline et le matching des bénéficiaires, pas la
couche d'affichage.
