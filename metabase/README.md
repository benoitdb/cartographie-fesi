# Stack Metabase — Cartographie FESI

Déploiement Metabase pour l'issue [#121](https://github.com/benoitdb/cartographie-fesi/issues/121)
(bascule Streamlit → Metabase, cohabitation ciblée). Phase 0 (schéma, chargement,
vues SQL), Phase 1 (dashboard national 2021-2027) et Phase 2 (vues régionales,
comparateur, volet national, vues pilotage) sont livrées ; Phase 3/4 restent à
faire (période 2014-2020, arbitrage final).

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
# dashboard national 2021-2027 (relançable sans effet de bord)
venv/bin/python setup_metabase.py
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
Nouvelle-Aquitaine/PON FSE avec Synergie), et cette fusion nationale reste un
sujet de Phase 2/3. Pas de filtre « période » ici : un dashboard 2014-2020
dédié est prévu en Phase 3.

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
  d'ambiguïté ici. À revoir en Phase 3.

**Init scripts appliqués sur une base déjà provisionnée** : `01_schema.sql`/
`02_views.sql`/`03_pilotage.sql` dans `metabase/init/` ne s'exécutent
automatiquement qu'à la création du volume Docker (`docker compose up` sur un
volume vierge). Sur une instance déjà démarrée, appliquer un nouveau fichier
à la main : `psql -h localhost -p 5437 -U <user> -d <db> -f metabase/init/03_pilotage.sql`.

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
  load_data.py          — charge data/processed/data.json dans PostgreSQL
  verify_aggregates.py  — recoupe les agrégats SQL vs JSON (Phase 0)
  setup_metabase.py     — provisionne Metabase : connexion, carte GeoJSON, 4 dashboards (Phase 1/2)
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
