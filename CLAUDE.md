# Cartographie FESI — fonds européens structurels et d'investissement

## Pourquoi

Dashboard d'exploration et de pilotage des opérations conventionnées FEDER /
FSE+ / FTJ sur la programmation 2021-2027 : où va l'argent, à qui, à quel
rythme de consommation. Portfolio / démo, pas un outil de production.

## État actuel

Dashboard Streamlit multipage fonctionnel (Accueil + Vue Régionale + Volet
National + Comparateur), alimenté par un pipeline Python qui transforme le
fichier XLSX source en JSON.

**La programmation 2014-2020 a son espace dédié** (`pages/5_Période_2014-2020.py`,
issue #83) : un écran, un sélecteur de périmètre en barre latérale (ensemble
national / volet national / une région), et non un sélecteur de période sur les
pages 2021-2027. Il n'y a **pas** de comparaison inter-périodes à outiller — les
logiques de programmation ont changé et REACT-EU a déformé la fin de période.
Les libellés de colonnes sont adaptés au chargement par `utils/periodes.py`, **par
source et non par période** depuis l'issue #95 (`RENOMMAGES` indexé sur une clé de
schéma — une période peut avoir plusieurs fichiers aux libellés différents, #68) ;
ce que la période n'a pas y est déclaré dans `CAPACITES` et retiré de l'écran, avec
son explication, et ce qu'une **source** 2014-2020 n'a pas en plus (`CAPACITES_SOURCE`
— trajectoire, rattachement départemental). Les **plafonds de cofinancement de la
période** y sont câblés depuis l'issue #81 (`categories_ue_2014_2020.json`, décision
2014/99), et le **pilotage** depuis l'issue #93 (dotations de l'Accord de partenariat
14-20 et maquettes REACT-EU transcrites). Reste absente la dimension thématique, que
la source ne porte pas (#82).

**Le rattachement départemental utilise désormais le champ Zone en repli**
(`dashboard/utils/departments.py`, issue #92) : avant le code postal du
bénéficiaire (siège du porteur, pas nécessairement le lieu du projet), la
cascade `assign_departement` essaie `zone_dept`, qui parse le champ Zone
Synergie (préfixes hiérarchiques `REG/DEPT/COMM/ARRDT/CANT/QUAR`, codes INSEE
réels). Validé sur les données réelles avant implémentation : 100 % d'accord
(zéro désaccord sur les cas comparables, 2014-2020 et 2021-2027) avec le champ
pipeline `Département de l'opération` déjà tenu pour fiable — Zone porte donc
la même localisation (lieu du projet), pas celle du bénéficiaire. Gain de
rattachement fiable en 2014-2020 : 13,0 % → 56,6 % (mieux que le 33 % de
2021-2027). Résout aussi la Corse sans ambiguïté (2A/2B explicite dans le code
Zone), là où `cp_to_dept` ne peut pas trancher un code postal préfixé `20`.
`assign_departement` étant partagée entre `pages/1_Vue_Régionale.py`
(2021-2027) et la page 2014-2020, le gain profite aux deux périodes — moindre
côté 2021-2027 (son champ pipeline est déjà mieux renseigné).

**Normandie, Nouvelle-Aquitaine et Bretagne lisent leur propre fichier régional
hors-Synergie** depuis l'issue #95, pas l'extraction Synergie qui les sous-comptait
fortement (Normandie en était même absente — #68) : toute la page 5, pas seulement
l'onglet Pilotage, bascule sur ce fichier pour ces trois périmètres (`utils/data_loader`,
loaders tolérants à son absence — gitignorés comme `data_2014-2020.json`, la CI
tourne sur un clone nu). Conséquence : leur millésime affiché est le leur, pas celui
de Synergie (22/08/2025, 31/05/2026 et 12/02/2024 contre 30/08/2023), et des capacités
leur manquent en propre — pas de date de programmation pour aucune des trois
(trajectoire retirée, jamais remplacée par la date de début, qui daterait autre
chose) et, pour Nouvelle-Aquitaine seule, ni code postal ni département (carte
départementale retirée). Bretagne a rejoint les deux autres en dernier (2026-08) :
son premier fichier régional (europe.bzh, 2022-06-09) n'avait ni numéro de dossier
ni code postal exploitable, contrairement à l'export officiel data.bretagne.bzh qui
l'a remplacé pour cet usage — resté ingéré à part et consultable sur la page
« Validation de la source » sous son propre identifiant (`2014-2020-bretagne`), le
temps de confirmer qu'il n'apporte plus rien.

**Le fichier PON FSE (hors Synergie, #68) porte sept programmes distincts, routés
chacun vers son périmètre depuis l'issue #95 (point 3)** — pas un seul périmètre
régional comme les trois fichiers ci-dessus, d'où une fusion **additive** avec
l'engagé Synergie plutôt qu'une substitution (`utils.periodes.REGIONS_PON_FSE_2014_2020`) :
les cinq PO FSE État des DROM (Réunion, Guadeloupe, Martinique, Guyane, Mayotte)
rejoignent l'engagé de leur région, PON FSE et PO IEJ national rejoignent le Volet
national. Ce dernier arbitrage — les garder agrégés au national plutôt que ventilés
par région — tient à leur dotation dans l'Accord de partenariat, une ligne
**nationale unique**, distincte des dotations IEJ *régionales* que portent déjà les
programmes FEDER-FSE gérés par les Conseils régionaux ; une vue par région de ces
deux programmes (carte, engagé sans taux) reste possible mais n'est pas construite
(issue #102). Mayotte n'a pas de PO FSE État séparé dans l'Accord (contrairement à
Guyane/Martinique/Réunion) : son engagé PON FSE se compare à la ligne FSE de son
programme combiné FEDER-FSE, seule dotation FSE que porte Mayotte.

Le pilotage 14-20 n'est donc plus masqué que sur « Ensemble national » — l'extraction
Synergie n'y fusionne aucune des trois régions hors-Synergie (#68). « Volet national »
en est sorti depuis que PON FSE et IEJ national y sont fusionnés : c'était la seule
pièce qui lui manquait. Un taux calculé sur un engagé partiel afficherait une donnée
manquante comme une sous-consommation. Normandie, Nouvelle-Aquitaine et Bretagne
retombent sur ce même masquage si leur fichier régional est absent du poste (repli,
pas un cas d'erreur). Le FSE breton affiche un taux au-dessus de 100 % (111 % au
12/02/2024) qui n'est pas une surconsommation mais un effet de granularité — ses sept
lignes sont des marchés de formation du Conseil régional, pas des opérations
unitaires (#95, point 2, non résolu par le changement de source) — signalé à l'écran
plutôt que masqué, comme les autres dépassements de la période (REACT-EU Normandie,
IEJ Nouvelle-Aquitaine).

**`main` est la référence** depuis la fusion de `streamlit-dashboard`
(PR #49, 2026-08-20) : elle porte le dashboard, ce fichier et les tests. Partir
de `main` et travailler sur une branche dédiée (`feat/...`, `fix/...`,
`test/...`), fusionnée par PR une fois la CI verte — pas de commit direct sur
`main` pour du code (les corrections de doc peuvent y aller directement).

`frontend/` est un **prototype React/Vite abandonné** au profit de Streamlit —
mais **il n'est pas mort** : le dashboard lit ses fichiers géographiques
(`frontend/public/geo/`). Ne pas supprimer ce dossier, et voir
`frontend/public/geo/SOURCES.md` pour la provenance de chaque contour.

**Déploiement Streamlit Community Cloud** (issue #119) : l'app est déployée sur
[share.streamlit.io](https://share.streamlit.io) — repo `benoitdb/cartographie-fesi`,
branche `main`, fichier `dashboard/Accueil.py`. Les 8 fichiers de données
principaux (~120 Mo, open data) sont committés dans le repo pour que Streamlit
Cloud les trouve directement. **Mise à jour des données** : quand un nouveau XLSX
sort (~5×/an), régénérer les JSON localement, committer et pousser — Streamlit
Cloud redéploie automatiquement sur push `main`. Le `requirements.txt` racine
renvoie vers `dashboard/requirements.txt` pour éviter la duplication.

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
  python ingest.py                        # XLSX 2021-2027 -> data.json
  python ingest.py 2014-2020-synergie     # XLSX Synergie  -> data_2014-2020.json
  python beneficiaires_fuzzy.py           # lit data.json, écrit beneficiaires_fuzzy.json
  python programme_totals.py              # Tableau 9B  -> programme_totals.json + programme_detail.json
  python dotations_os_totals.py           # Tableau 8   -> dotations_os.json
  python interreg_totals.py               # Tableau 10  -> interreg.json
  python transferts_solidarite_totals.py  # Tableau 3A/3B -> transferts_solidarite.json
  python categories_ue_2014_2020.py       # Décision 2014/99 -> categories_ue_2014_2020.json
  python programme_totals_2014_2020.py    # Accord 14-20 + maquettes REACT-EU
                                          #   -> programme_totals_2014_2020.json
                                          #    + programme_detail_2014_2020.json
  ```
- **Profil d'une source** (page « Validation de la source »), un JSON **committé**
  par fichier source, à régénérer à chaque nouveau millésime :
  ```
  python profil_source.py 2021-2027-conventionnees
  python profil_source.py 2014-2020-synergie
  ```
  Les identifiants sont les clés de `sources.SOURCES`.
- **`region_metadata.py`** est un script **one-shot** qui appelle Wikidata par
  le réseau. Ne pas le lancer dans une régénération de routine : son résultat
  est committé exprès pour que le dashboard tourne sans dépendance externe.
  À relancer une fois par an environ.

- **Tests** : `venv/bin/python -m pytest -q` (376 tests, ~40 s). Ils tournent sur
  un clone nu et en CI : aucun ne lit le XLSX ni les JSON générés. Ceux du
  pipeline éprouvent la logique sur des cas construits ; ceux du dashboard
  lisent les fixtures committées dans `tests/fixtures/` (**une par période** —
  voir son README, **à régénérer quand le schéma d'un `data*.json` change**).
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
- `data-pipeline/` — scripts de transformation, un par sortie JSON.
  `agregats.py`, `schema_source.py` et `sources.py` font exception : ce sont des
  modules importés (par `ingest.py`, et par le générateur de fixture pour le
  premier), pas des scripts à lancer.
  **`sources.py` décrit chaque fichier source une seule fois** — motif de nom,
  feuille, période (donc schéma), date d'extraction, table programme → région.
  `ingest.py` et `profil_source.py` le lisent tous les deux : les deux doivent
  lire le même fichier de la même façon, sinon le profil atteste une donnée qui
  n'est pas celle qu'on a ingérée. Ajouter une source = une entrée dans
  `SOURCES`, pas un second script.
- `data-pipeline/reference/` — **données réglementaires saisies à la main**
  depuis l'Accord de partenariat 2021-2027 (tableaux 3A/3B, 8, 9B, 10), NUTS,
  catégories de cohésion UE. C'est la source de vérité des montants *programmés*,
  par opposition aux montants *engagés* qui viennent du XLSX.
- `data/raw/` — le XLSX source, **non versionné**
- `data/processed/` — JSON générés, **un par période** (`data.json` =
  2021-2027, `data_2014-2020.json`) : les fusionner chargerait ~100 Mo en
  mémoire Streamlit à chaque page pour n'en afficher qu'une. Tous les JSON
  sont committés (open data, nécessaire au déploiement Streamlit Cloud — voir
  les commentaires du `.gitignore`). Le XLSX source reste gitignoré
- `docs/sources/` — notes de travail sur les documents de référence, non versionné

## Pièges non devinables

- **Un clone frais tourne** depuis l'issue #119 : les JSON de données sont
  committés (open data, ~120 Mo). Le XLSX source reste gitignoré — le
  régénérer demande de le récupérer et de relancer le pipeline.
- **Source du XLSX** :
  [europe-en-france.gouv.fr — liste des opérations FEDER/FSE+/FTJ 2021-2027](https://www.europe-en-france.gouv.fr/fr/ressources/liste-operations-feder-fse-ftj-2021-2027).
  Version utilisée : `20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx`.
- **Le fichier est republié 5 fois par an, en « annule et remplace »** — nouveau
  nom de fichier daté à chaque fois. `ingest.py` retient désormais le millésime
  le plus récent de `data/raw/` et **affiche lequel** au démarrage
  (`sources.trouver_fichier`, issue #47) : lire cette ligne avant
  toute conclusion sur des chiffres. Le millésime est aussi propagé jusqu'au
  dashboard (`metadata.millesime` → `utils/millesime.py`), qui l'affiche en pied
  de barre latérale sur chaque page — **ne pas retirer cet affichage** : c'est
  la seule chose qui distingue à l'écran des chiffres du jour d'un export vieux
  de plusieurs mois. Déposer le nouvel export suffit, mais
  l'ancien reste présent tant qu'on ne le supprime pas.
- **`ingest.py` mappe les colonnes par index, pas par nom** (choix assumé, jugé
  plus fiable que des libellés instables). Ce mapping est **vérifié** contre les
  libellés attendus au démarrage (`schema_source.build_cols`, issue #45) : un
  réordonnancement de la source fait échouer le pipeline avec un message qui
  nomme la position fautive, au lieu de produire des données fausses en silence.
  La comparaison ignore casse, espaces et type d'apostrophe — le fichier source
  mélange déjà `'` et `’`. Si la source change légitimement, mettre à jour le
  schéma de sa période (`schema_source.SCHEMAS`) après avoir vérifié à quoi
  correspond chaque colonne.
- **Le schéma dépend de la période, pas du projet** (issue #12) :
  `schema_source.SCHEMAS` porte une liste de colonnes par période — 23 colonnes
  en 2021-2027, 19 en 2014-2020, dans un ordre différent. Les clés internes sont
  communes quand la colonne l'est, mais **2014-2020 n'a ni objectif stratégique,
  ni taux de cofinancement, ni date de première convention** (sa dimension
  thématique est le `Domaine d'intervention`, et sa date de référence celle de la
  programmation) : tout code aval doit tester la présence d'une clé, jamais la
  supposer. `build_cols(colonnes)` sans schéma reste 2021-2027.
  Les libellés de 2014-2020 sont vérifiés dans les tests contre un **relevé
  indépendant** des colonnes du fichier : les tests dérivant leurs libellés du
  schéma lui-même ne peuvent pas voir une transcription fausse (constaté par
  mutation). Reconduire ce relevé pour toute nouvelle période.
- **`harmonize_region` prend la table programme → région de sa période**
  (`programme_index`, construit une fois par `indexer_programmes`). En 2021-2027
  c'est un repli marginal ; en **2014-2020 c'est la voie principale**, la colonne
  région n'y étant remplie qu'à 16,4 %. Oublier de passer l'index de la période
  ne lève rien : ça rattache 20 821 opérations au Volet national. `ingest.py` le
  passe explicitement, depuis le descripteur de source.
- **2014-2020 n'est pas 2021-2027 en plus vieux** (issue #12). Un seul pipeline,
  paramétré par source — pas un second script. Ce qui change, et qui se paie
  cher si on l'oublie :
  - les données sont sur la **2ᵉ feuille** du fichier Synergie, la feuille 0
    étant une notice (lire l'index 0 par défaut donnerait un DataFrame de
    notice, sans erreur) ;
  - **pas de dimension thématique** : la colonne `Domaine d'intervention` est
    vide à 0,0 %. Les blocs `by_objectif_strategique` / `by_region_objectif` /
    `by_fonds_objectif` sont **absents** de la sortie, et `metadata` porte
    `dimension_thematique: null`. Ne jamais inventer de « Non spécifié » pour
    homogénéiser la forme entre périodes ;
  - **six fonds** — FEDER, FSE, IEJ, FEAD, FEDER REACT-EU, FEDER-FSE — et non
    FEDER/FSE+/FTJ. **Trois d'entre eux échappent aux plafonds de l'article 120**
    (`utils/cofinancement.FONDS_HORS_PLAFOND`), chacun pour une raison écrite
    dans un texte : REACT-EU y déroge (jusqu'à 100 %, règlement 2020/2221
    art. 92 ter §12) ; l'IEJ voit son plafond **relevé** par l'art. 120 §3
    lui-même ; le FEAD n'est pas un Fonds ESI mais un transfert hors enveloppe
    structurelle (art. 94), régi par le règlement 223/2014. Les leur appliquer
    produit un faux positif garanti — c'est ce que l'issue #81 devait éviter ;
  - **un plafond se fixe par axe prioritaire, pas par opération**, et l'art. 120
    §5 le majore de **dix points** quand un axe est entièrement mis en œuvre par
    instruments financiers ou par développement local. Le fichier ne porte pas
    l'axe : un dépassement affiché est un écart à expliquer, jamais un constat ;
  - la colonne région n'est remplie qu'à **16,4 %** : c'est le libellé du
    programme qui rattache le reste ;
  - **le périmètre Synergie est incomplet** (#68) : Bretagne (3 opérations) et
    Nouvelle-Aquitaine (25) n'apparaissent qu'à la marge, leurs autorités de
    gestion n'utilisant pas SynergieCDM. Ne pas lire ces totaux comme la
    réalité de ces régions ;
  - les 5 programmes interrégionaux tombent au Volet national (#77) ;
  - **l'IEJ compte double.** La ligne `IEJ` de l'Accord ne porte que
    l'allocation spécifique (471 474 337 € au national) ; la contrepartie FSE,
    de montant quasi égal (473 185 393 €), est sur la ligne `FSE` du même
    programme (§1.4.2 et table 1.10). Une opération IEJ consomme les deux : le
    dénominateur IEJ les additionne, et le FSE en est diminué d'autant, sinon
    la contrepartie est comptée deux fois et l'IEJ affiche ~200 % ;
  - **le libellé `FEDER REACT-EU` n'existe que dans les DROM** (Guadeloupe,
    La Réunion, Martinique, Mayotte). En métropole les mêmes opérations sont
    rangées sous `FEDER` — le FEDER métropolitain y dépasse sa dotation de 26 à
    87 %, d'un excédent qui vaut à peu près la maquette REACT-EU de la région.
    D'où `periodes.fusionner_enveloppes_sans_libelle` : une enveloppe rejoint le
    fonds qui porte ses opérations, et à défaut son fonds d'origine (#96) ;
  - **deux fonds engagés n'ont aucune enveloppe**, et doivent rester absents de
    tout rapprochement plutôt qu'affichés à zéro : le **FEAD** (transfert hors
    enveloppe structurelle, art. 94) et le **FEDER-FSE**, qui n'est pas un fonds
    mais le libellé des opérations du PNAT Europ'Act.
- **Programmé ≠ engagé.** En 2021-2027 les montants programmés viennent de
  l'Accord de partenariat dans sa version **préliminaire** de juin 2022,
  probablement révisée depuis. Tout taux de consommation est une estimation : la
  réserve méthodologique (`utils.pilotage.RESERVE_METHODO`) doit rester affichée
  à côté, ne jamais la retirer pour gagner de la place.
  En 2014-2020 la provenance est **double et de natures différentes** : dotations
  de l'Accord 14-20 (texte négocié en amont, version 4 d'octobre 2019) pour le
  FEDER, le FSE et l'IEJ, et maquettes REACT-EU relevées par une **évaluation**
  (ANCT, décembre 2024), donc constatées en fin de période après décisions
  modificatives. `periodes.MENTION_PROVENANCE_ENVELOPPES` le dit à l'écran et
  tient le même rôle que `RESERVE_METHODO` : ne pas la retirer.
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

Sur un changement touchant le pipeline, la vérification qui compte reste de
**régénérer `data.json` et de le comparer au bit près** à une copie prise avant
modification (`aggregates` et `operations`). Les tests couvrent désormais le
calcul d'agrégats, mais sur des cas construits : seule la régénération éprouve
le pipeline sur les 16 625 opérations réelles.

**GitHub issues — AI-driven dev, pas du vibe-coding** : toute limitation
connue, gotcha, piste d'évolution ou choix technique non trivial pris de façon
autonome est loggé comme issue sur `benoitdb/cartographie-fesi`, par défaut,
sans attendre qu'on le demande. Objectif : que l'utilisateur reste le décideur
capable d'expliquer et de ré-arbitrer un choix plus tard. Les issues servent
aussi de backlog de pistes explorées et bloquées (source manquante, donnée
absente) — les documenter comme telles plutôt que de les abandonner en silence.

**Couverture de test, état** : le pipeline est couvert sur ses points de
rupture silencieuse — schéma du fichier source, harmonisation des régions,
rapprochement des bénéficiaires, et **calcul d'agrégats** depuis son extraction
dans `data-pipeline/agregats.py` (PR #65, issue #60). Ce module est le seul
endroit où se calculent les totaux servis au dashboard : `ingest.py` l'appelle,
et `tests/fixtures/generer_fixture.py` aussi, ce qui rend la fixture de test
auto-cohérente.

**La couche de calcul est couverte** depuis la PR #63 :
`tests/test_stats_calculs.py`, `tests/test_cofinancement_regles.py`,
`tests/test_pilotage_calculs.py` (58 tests sur des cas construits, valeurs
attendues posées à la main). Priorité y est donnée aux invariants documentés et
aux régressions déjà constatées : bornes IQR par fonds, montant manquant devenu
`NaN`, reste à engager calculé par fonds, dépassement d'enveloppe jamais
tronqué. **Chaque test a été vu échouer** sur une mutation du code qu'il
protège, avant d'être livré — un test vert qui ne peut pas rougir ne protège
rien.

Les règles de calcul du pilotage (`reste_a_engager`, `taux_consommation`) sont
sorties du rendu et testées directement (issue #62) ; le test `AppTest` qui reste
ne garde que le câblage jusqu'à l'écran. **Faire de même pour tout calcul qu'on
ajouterait dans une fonction `render_*`** : une règle métier ne se teste pas à
travers une chaîne de caractères affichée.

Restent hors couverture, sciemment : la mise en forme des figures (couleurs,
libellés, survols) hors des cas où elle porte un calcul, et les fonctions de
`stats.py` purement graphiques (histogramme, boîte à moustaches, nuages,
Pareto, Lorenz) — leur justesse se voit à l'écran, pas dans une assertion.
