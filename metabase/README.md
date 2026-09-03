# Stack Metabase — Cartographie FESI

Déploiement Metabase pour l'issue [#121](https://github.com/benoitdb/cartographie-fesi/issues/121)
(bascule Streamlit → Metabase, cohabitation ciblée). Les cinq phases sont
livrées : schéma et chargement (Phase 0), dashboard national 2021-2027
(Phase 1), vues régionales/comparateur/volet national (Phase 2), période
2014-2020 — fusion des six sources, cofinancement (Phase 3), et validation
croisée Streamlit ↔ Metabase avec arbitrage des cinq écarts trouvés (Phase 4).
Quelqu'un qui veut juste **utiliser** les dashboards peut aller directement à
la section « Guide utilisateur » ci-dessous ; le reste de ce fichier
documente comment la stack a été construite.

## Pré-requis

### Docker

Si Docker n'est pas installé :

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose-v2

# Vérifier
docker --version          # Docker 24+
docker compose version    # Compose v2+
```

Ajouter son utilisateur au groupe `docker` pour éviter `sudo` :

```bash
sudo usermod -aG docker $USER
newgrp docker   # active le groupe dans la session courante
```

> **Note :** `newgrp` n'agit que dans le shell courant. Les autres terminaux
> (y compris les outils qui lancent des commandes dans un sous-shell) ne voient
> le groupe qu'après un logout/login complet.

### Python

```bash
cd metabase/
python3 -m venv venv
venv/bin/pip install psycopg2-binary requests
```

## Lancement

```bash
cd metabase/

# Démarrer PostgreSQL + Metabase + serveur GeoJSON
# (premier lancement : ~550 Mo de téléchargement)
docker compose up -d

# Vérifier que les trois containers tournent
docker compose ps

# Charger les données FESI dans PostgreSQL
venv/bin/python load_data.py

# Provisionner Metabase : connexion PostgreSQL, carte GeoJSON métropole,
# les 5 dashboards (relançable sans effet de bord)
venv/bin/python setup_metabase.py

# Vérifier (facultatif) : agrégats SQL vs JSON, puis fusion 14-20 SQL vs dashboard
venv/bin/python verify_aggregates.py
venv/bin/python verify_pilotage_2014_2020.py

# Vérification de bout en bout : chaque carte de chaque dashboard interrogée par
# l'API, filtres appliqués, contre ce qu'affiche Streamlit. Se lance depuis la
# RACINE du dépôt et avec le venv racine — il lui faut Streamlit (les règles de
# pilotage y sont importées, pas réécrites) et pas psycopg2.
cd .. && venv/bin/python metabase/verify_dashboards.py
```

## Accès à Metabase

Metabase est accessible sur **http://localhost:3000**.

Au premier accès, Metabase demande une configuration initiale. Identifiants
configurés par le setup automatique :

| Paramètre | Valeur |
|-----------|--------|
| Email | `admin@fesi.local` |
| Mot de passe | voir `.env` (`MB_ADMIN_PASSWORD`) |

La connexion à la base FESI est déjà configurée (ajoutée via l'API au setup).

**Credentials :** tous dans `.env` (gitignoré). Ne pas coder de mot de passe
en dur dans les fichiers versionnés.

## Guide utilisateur — quel dashboard pour quoi

**Répartition des rôles** (voir aussi l'[étude d'impact](https://claude.ai/code/artifact/2ad9ab38-a0fc-4697-ab26-651c57d952bb)) :
Metabase couvre la consultation courante — KPI, filtres, drill-down, pilotage
programmé vs engagé. Streamlit garde pour l'instant les analyses statistiques
avancées (Pareto, Lorenz, IQR, détection d'anomalies) et les choroplèthes
DROM-COM en encarts ; [#129](https://github.com/benoitdb/cartographie-fesi/issues/129)
en ramène la plus grande part dans Metabase, phase par phase. Les deux lisent
la même base PostgreSQL — jamais deux calculs séparés du même chiffre.

**Cinq dashboards, organisés par question posée** et non par page Streamlit
([#129](https://github.com/benoitdb/cartographie-fesi/issues/129)). La
**période** et le **périmètre** y sont des **paramètres**, pas des écrans :

| Dashboard | Quand l'ouvrir |
|---|---|
| FESI — Territoires | Où va l'argent : carte des régions, classement des périmètres, détail d'un périmètre. |
| FESI — Structure & répartition | Comment se répartit l'enveloppe : par fonds, puis (phase C) par thématique et par programme. |
| FESI — Pilotage | Où en est la consommation : programmé vs engagé, trajectoire, comparaison entre périmètres. |
| FESI — Analyses & contrôle | Ce que la moyenne cache : cofinancement face au plafond, puis (phase D) distribution, concentration, cohérence. |
| FESI — Qualité des sources | D'où viennent les chiffres : sources chargées, champs non renseignés. |

L'instance ouvre sur **FESI — Accueil**, une page de garde qui renvoie vers les
cinq. Tout est rangé dans la collection **FESI** ; le contenu d'exemple livré
avec Metabase reste où il est.

**Les trois filtres, communs à tous les dashboards :**

- **Période** — `2021-2027` par défaut. Sans valeur, les cartes somment les
  deux périodes, ce qui ne veut rien dire : 2014-2020 est close, 2021-2027 en
  cours.
- **Périmètre** — une région, `national` (programmes nationaux) ou
  `interregional`. **Il accepte plusieurs valeurs** : comparer deux régions,
  c'est en cocher deux. C'est ce qui a fait disparaître l'ancien écran
  Comparateur. Sans valeur, le chiffre porte sur toute la période.
- **Fonds** — FEDER / FSE+ / FTJ en 2021-2027, FEDER / FEDER REACT-EU / FSE /
  IEJ en 2014-2020. Un même graphique montre donc des séries différentes selon
  la période : ce n'est pas une anomalie.

**Trois cartes ignorent volontairement un filtre**, et leur libellé le dit sur
le dashboard :

- *Engagement cumulé 2021-2027* ignore **Période** (scopée en dur ; une
  trajectoire 2014-2020 demanderait des dates sur le périmètre fusionné des six
  sources — phase C) ;
- *Taux de consommation par périmètre* ignore **Périmètre** (elle sert à situer
  un périmètre parmi tous les autres) ;
- *Dépassements de plafond de cofinancement* ignore **Période** : le plafond de
  l'art. 120 du règlement 1303/2013 s'adosse aux catégories de cohésion de
  2014-2020.

**Sans filtre Périmètre sur la période 2014-2020**, le chiffre couvre le pays
entier, régions et volet national fusionnés — ce que l'ancien écran appelait
« Ensemble national » via une valeur sentinelle, devenue inutile avec un filtre
non obligatoire. Les deux réserves de lecture, elles, restent entières.

**« Ensemble national » — deux réserves à connaître avant de lire ce
périmètre** (arbitrage Phase 4, [#121](https://github.com/benoitdb/cartographie-fesi/issues/121)) :
1. **Bretagne compte différemment.** Son fichier regroupe les opérations en
   marchés de formation plutôt qu'en dossiers individuels — son nombre de
   projets et son montant moyen ne se comparent pas terme à terme aux autres
   régions dans cet agrégat.
2. **Six millésimes différents.** Les six sources qui composent ce total ont
   été extraites entre 2023 et 2026 — l'agrégat mélange des photos prises à
   des moments différents, pas un instantané unique.

La carte et le classement par région du dashboard Streamlit équivalent
n'incluent pas encore la part PON FSE des DROM sur ce même périmètre —
écart connu, journalisé dans l'issue [#128](https://github.com/benoitdb/cartographie-fesi/issues/128),
pas dans le KPI ni le pilotage.

**Le taux de cofinancement affiché est toujours recalculé** (montant UE /
dépenses éligibles), jamais le taux déclaré par un fichier source — même sur
les trois régions (Bretagne, Normandie, Nouvelle-Aquitaine) dont le fichier en
déclare un. Un écart notable entre les deux est signalé à part sur la page
Streamlit, jamais substitué au recalculé ([#127](https://github.com/benoitdb/cartographie-fesi/issues/127),
fermée). Les dépassements de plafond de cofinancement appliquent une
tolérance d'un millionième — une opération programmée pile au plafond ne doit
pas apparaître en dépassement à cause d'un arrondi à la centime côté source
([#126](https://github.com/benoitdb/cartographie-fesi/issues/126), fermée).

### Historique de construction — les écrans des Phases 1-3

> Les cinq sections qui suivent décrivent les dashboards des Phases 1-3, **dissous
> par [#129](https://github.com/benoitdb/cartographie-fesi/issues/129)** au profit
> de l'organisation par usage ci-dessus. `setup_metabase.archive_legacy()` les
> archive (archivage réversible, pas suppression). Elles sont conservées pour qui
> construit ou reprend le provisionnement : les arbitrages de calcul qu'elles
> documentent (dates d'engagement, `fonds IS NOT NULL`, taux recalculé, tolérance
> de plafond) valent toujours, ce sont les mêmes que portent les cartes actuelles.

### Dashboard national 2021-2027 (Phase 1, issue #121)

`setup_metabase.py` crée 5 questions sauvegardées et 1 dashboard, tous scopés
à `source_id = '2021-2027-conventionnees'` :

- **Nombre d'opérations**, **Montant UE total** (scalaires, `v_by_fonds` sommé)
- **Montant UE par fonds** (bar chart, couleurs = `FONDS_COLORS` importé
  directement depuis `dashboard/utils/themes.py` — jamais dupliqué)
- **Engagement cumulé** (courbe mensuelle cumulée sur `date_convention` ;
  exclut les opérations sans date de convention)
- **Montant UE par région** (choroplèthe, carte GeoJSON métropole)

Dashboard **« FESI — Vue nationale 2021-2027 »**, avec un filtre paramétrique
**Fonds** (FEDER/FSE+/FTJ) mappé sur les 5 cartes via un template-tag SQL
`{{fonds}}`. Relancer le script après toute modification des questions pour
les remettre dans cet état (recherche par nom, idempotent).

**Portée volontairement limitée à 2021-2027** : les vues Phase 0 sont scopées
par `(source_id, periode)` et ne blendent jamais plusieurs sources pour une
période — 2014-2020 a 5 sources qui se chevauchent (Bretagne/Normandie/
Nouvelle-Aquitaine/PON FSE avec Synergie). Pas de filtre « période » ici : la
fusion de ces sources est faite par les vues dédiées de la Phase 3
(`04_periode_2014_2020.sql`), alimentant un dashboard 2014-2020 **séparé** —
pas un sélecteur de période sur ce dashboard-ci, exactement comme le dashboard
Streamlit garde la période 14-20 sur son propre écran (#83).

**Vérifié** (recoupement API Metabase vs SQL direct, pas seulement visuel) :
16 625 opérations, 7 879 820 894,76 € au total pour 2021-2027 ; filtre
`fonds=FEDER` → 6 038 opérations — identique des deux côtés.

### Vues régionales, comparateur, volet national (Phase 2, issue #121)

Trois dashboards supplémentaires, tous scopés à `2021-2027` :

- **« FESI — Vue régionale 2021-2027 »** — équivalent Metabase de
  `pages/1_Vue_Régionale.py` : KPI (montant, nombre d'opérations) et pilotage
  (programmé vs engagé, taux, reste à engager par fonds) pour **une** région,
  choisie via un template-tag texte `region` (même pattern que `fonds` en
  Phase 1 — pas de field-filter, cf. gotchas ci-dessous).
- **« FESI — Comparateur régions 2021-2027 »** — équivalent de
  `pages/3_Comparateur.py` : deux template-tags indépendants (`region_a`,
  `region_b`) sur des cartes **communes** (région en série/dimension), pas
  deux jeux de cartes dupliqués — montant par fonds, taux de consommation,
  table KPI comparant les deux régions choisies côte à côte.
- **« FESI — Volet national 2021-2027 »** — équivalent de
  `pages/2_Volet_National.py` : périmètre fixe (`perimetre = 'national'`,
  même clé que `programme_totals`), pas de template-tag région. Pas de ligne
  FEDER pour ce périmètre (les opérations nationales sont des programmes
  FSE+/FTJ, ex. France Travail) — cohérent avec `v_pilotage`.

**Vues SQL pilotage** (`metabase/init/03_pilotage.sql`) :
- `v_engage_by_perimetre_fonds` — engagé par (période, périmètre, fonds), où
  périmètre = région **ou** `'national'` (même clé que `programme_totals`,
  pour pouvoir les joindre directement).
- `v_pilotage` — jointure `programme_totals` / `v_engage_by_perimetre_fonds` :
  `programme`, `engage`, `taux` (`engage / programme`, jamais plafonné — un
  dépassement est un signal, pas une anomalie) et `reste_a_engager` (calculé
  **par fonds**, planché à 0, puis à sommer si besoin — jamais
  `programme_total - engage_total`, qui masquerait un reliquat sur un fonds
  derrière un dépassement sur un autre, cf. `dashboard/utils/pilotage.py`
  et l'issue #62). **Vérifiée** contre le cas documenté dans ce module :
  Auvergne-Rhône-Alpes FEDER 2021-2027, ~141 M€ de reste à engager malgré un
  dépassement FSE+.
  Scopée à 2021-2027 en pratique : elle agrège l'engagé sans distinguer les
  sources d'une période, ce qui redonnerait le double-comptage évité par
  `02_views.sql` (#68/#95) si on l'utilisait telle quelle sur 2014-2020 (5
  sources qui se chevauchent) — 2021-2027 n'a qu'une source, donc pas
  d'ambiguïté ici. **C'est ce que lève la Phase 3 ci-dessous**, avec des vues
  dédiées à la période plutôt qu'en élargissant celles-ci.

### Période 2014-2020 (Phase 3, issue #121)

Dashboard **« FESI — Période 2014-2020 »**, équivalent Metabase de
`pages/5_Période_2014-2020.py` : KPI (montant programmé, nombre d'opérations),
montant par fonds, pilotage programmé vs engagé, et dépassements de plafond de
cofinancement — pour **un** périmètre choisi via un template-tag texte
`perimetre` (une région, ou `'national'` pour le volet national ; même pattern
que `region` en Phase 2). Les six sources de la période y sont **fusionnées**,
là où Phase 1/2 restaient scopées à une source unique.

**Vues SQL** (`metabase/init/04_periode_2014_2020.sql`) :
- `v_perimetre_2014_2020` — une ligne par opération, taguée de son périmètre
  final. C'est là que vivent les deux règles de fusion de la période :
  **substitution** (Bretagne/Normandie/Nouvelle-Aquitaine lisent leur fichier
  régional et ignorent entièrement Synergie, qui ne les couvre qu'à la marge)
  et **addition** (le PON FSE s'ajoute, routé par `libelle_programme` et non
  par la région portée sur chaque ligne : les cinq PO FSE État des DROM vers
  leur région, PON FSE et PO IEJ national vers le volet national). Les
  opérations interrégionales sont exclues des totaux régionaux, comme côté
  Python — sinon elles compteraient dans plusieurs totaux censés s'additionner.
  Le vieux fichier Bretagne (`2014-2020-bretagne`, europe.bzh) n'y entre
  jamais : remplacé par `2014-2020-bretagne-officiel` pour tout usage autre que
  la page « Validation de la source ».
- `v_engage_2014_2020` — l'engagé par (périmètre, fonds), agrégé là-dessus.
- `v_enveloppes_2014_2020` — les enveloppes de `programme_totals`, après fusion
  **FEDER REACT-EU → FEDER** sur les seuls périmètres qui ne portent aucune
  opération étiquetée `FEDER REACT-EU` (seuls les DROM en ont une dans
  Synergie ; en métropole les mêmes opérations sont rangées sous FEDER, cf.
  `periodes.FUSIONS_ENVELOPPES_SANS_LIBELLE` et #96). La correction IEJ
  (contrepartie FSE retranchée du FSE et ajoutée à l'IEJ) est déjà faite en
  amont par `programme_totals_2014_2020.py` : rien à refaire ici.
- `v_pilotage_2014_2020` — même formule que `v_pilotage`. FEAD et FEDER-FSE
  n'y apparaissent jamais, faute d'enveloppe en face (le premier hors Fonds
  ESI, le second pas un fonds mais le libellé du PNAT Europ'Act).
- `v_cofinancement_2014_2020` / `_summary` — taux par opération face au plafond
  de sa région (art. 120 §3), avec les trois fonds hors champ exclus
  (`FEDER REACT-EU`, `IEJ`, `FEAD` — cf. `cofinancement.FONDS_HORS_PLAFOND`).
  Part de `v_perimetre_2014_2020`, pas d'`operations` : sinon le vieux fichier
  Bretagne et les opérations Synergie marginales des régions substituées
  s'ajouteraient à celles déjà comptées. `depasse_plafond` compare au plafond
  **maximum** de la fourchette (six régions modernes sur treize réunissent
  d'anciennes régions de catégories différentes) : le plafond se fixe par axe
  prioritaire et peut être majoré de dix points (§5), comparer au minimum
  multiplierait les faux positifs. Un dépassement reste un écart à expliquer,
  jamais un constat.

La table `categories_ue_2014_2020` (région → catégorie de cohésion de l'époque
et plafond min/max) est chargée par `load_data.py`, qui appelle directement
`dashboard/utils/cofinancement.plafond_intervalle_2014_2020` plutôt que de
retranscrire la règle.

**Vérifié** par `verify_pilotage_2014_2020.py` (tests croisés Python vs SQL,
même esprit que la Phase 0 mais sur la *fusion* des sources) : 68 couples
(périmètre × fonds) engagés et 55 enveloppes concordent, règles relues du
dashboard plutôt que réimplémentées. Le script a été **vu rougir** sur une
mutation de `v_perimetre_2014_2020` (substitution retirée : Bretagne et
Nouvelle-Aquitaine repassent en double-comptage) avant d'être livré vert.
Recoupé aussi via l'API Metabase : Bretagne FSE ressort à **111 %** sur
**7 opérations**, exactement ce que documente
`periodes.MENTION_BRETAGNE_FSE_GRANULARITE` côté Streamlit (marchés de
formation du Conseil régional, pas des opérations unitaires — un effet de
granularité, pas une surconsommation) ; Auvergne-Rhône-Alpes FEDER affiche
740 072 469 € programmés, soit bien la somme FEDER + maquette REACT-EU fondue,
quand La Réunion garde ses deux lignes séparées.

**Init scripts appliqués sur une base déjà provisionnée** : les fichiers de
`metabase/init/` ne s'exécutent automatiquement qu'à la création du volume
Docker (`docker compose up` sur un volume vierge). Sur une instance déjà
démarrée, appliquer un nouveau fichier à la main :
`psql -h localhost -p 5437 -U <user> -d <db> -f metabase/init/04_periode_2014_2020.sql`.

## GeoJSON

Metabase bloque les URL internes (protection SSRF) — les hostnames Docker
et les IP privées ne passent pas. `setup_metabase.py` enregistre la carte
métropole (`fesi_metropole`) via son URL GitHub Raw publique
(`https://raw.githubusercontent.com/benoitdb/cartographie-fesi/main/
frontend/public/geo/regions-metropole.geojson`), identifiant de région `nom`
des deux côtés (correspond exactement à la colonne `region` en base).

Seule la carte métropole est en scope Phase 1 (cf. issue #121). Les cartes
DROM-COM/départements testées en Phase 0 ne sont pas (re)provisionnées ici —
même limite déjà actée : pas d'encart DROM-COM en carte unique dans Metabase,
chaque territoire nécessiterait sa propre question.

## Structure

```
metabase/
  docker-compose.yml    — PostgreSQL 16 + Metabase + serveur GeoJSON
  .env                  — credentials locaux (gitignoré)
  init/
    01_schema.sql       — schéma fesi : tables operations, programme_totals, region_metadata
    02_views.sql        — vues d'agrégats scopées (source_id, periode)
    03_pilotage.sql     — vues pilotage (programmé vs engagé, taux, reste à engager) — Phase 2
    04_periode_2014_2020.sql — fusion des six sources 14-20, pilotage et
                          cofinancement de la période, table categories_ue — Phase 3
  load_data.py          — charge les JSON de data/processed/ dans PostgreSQL
  verify_aggregates.py  — recoupe les agrégats SQL vs JSON, source par source (Phase 0)
  verify_pilotage_2014_2020.py — recoupe la fusion 14-20 SQL vs dashboard (Phase 3)
  verify_dashboards.py  — recoupe les cartes Metabase (via l'API, filtres appliqués)
                          vs le dashboard Streamlit, 461 valeurs (Phase 4)
  setup_metabase.py     — provisionne Metabase : connexion, carte GeoJSON, 5 dashboards (Phase 1/2/3)
  venv/                 — environnement Python (gitignoré)
  README.md             — ce fichier
```

## Arrêt / nettoyage

```bash
# Arrêter (données conservées dans le volume pgdata)
docker compose down

# Arrêter ET supprimer les données
docker compose down -v
```

## Schéma PostgreSQL

### Table `operations`

| Colonne | Type | Source JSON |
|---------|------|-------------|
| `region` | TEXT | `regions_modernes[0]` |
| `fonds` | TEXT | `Fonds` |
| `montant_ue` | NUMERIC | `Montant UE` |
| `depenses_eligibles` | NUMERIC | `Total des dépenses éligibles` |
| `objectif_strategique` | TEXT | `Objectif stratégique` |
| `date_premiere_convention` | DATE | `Date première convention` |
| `is_interregional` | BOOLEAN | `is_interregional` |
| `is_national` | BOOLEAN | `is_national` |
| ... | | (27 colonnes au total) |

### Table `programme_totals`

Enveloppes programmées par région et fonds (Accord de partenariat).

### Table `region_metadata`

Population, superficie, chef-lieu, catégorie UE par région (Wikidata).
