# Test local Metabase — Cartographie FESI

Test de faisabilité pour l'issue [#121](https://github.com/benoitdb/cartographie-fesi/issues/121).

**Objectif :** valider que Metabase peut afficher une region map à partir du
GeoJSON métropole existant (`frontend/public/geo/regions-metropole.geojson`),
et explorer les capacités BI sur les données FESI.

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
venv/bin/pip install psycopg2-binary
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

### Contenu créé par le script de test

- **4 questions sauvegardées** : Montant UE par région, Répartition par fonds,
  KPI nationaux, Engagement cumulé
- **1 dashboard** : « FESI — Vue nationale (test) » assemblant les 4 questions

## Test du GeoJSON

Metabase bloque les URL internes (protection SSRF) — les hostnames Docker
et les IP privées ne passent pas. Deux approches possibles :

**Via l'API** (utilisée ici) : référencer les GeoJSON par leur URL GitHub Raw
publique (`https://raw.githubusercontent.com/benoitdb/cartographie-fesi/main/
frontend/public/geo/...`). Le script de setup les enregistre automatiquement.

**Via l'interface admin** : Admin > Paramètres > Cartes > Ajouter une carte,
puis coller l'URL publique. Region identifier : `nom`, Region name : `nom`.

### Résultat du test (1er sept. 2026)

- **Choroplèthe métropole : fonctionne.** Le GeoJSON (13 régions, propriétés
  `code` et `nom`) est compatible — chaque feature a un identifiant textuel
  (`nom`) qui correspond exactement aux valeurs de la colonne `region` en base.
- Les 3 cartes (métropole, DROM-COM, départements) sont enregistrées et
  fonctionnelles.
- Dashboard de test créé avec 5 visualisations : KPI, bar chart fonds, tableau
  par région, courbe d'engagement cumulé, carte choroplèthe.
- **Limite confirmée** : pas d'encarts DROM-COM en carte unique — chaque
  territoire nécessite une question séparée ou une carte distincte.

## Structure

```
metabase/
  docker-compose.yml    — PostgreSQL 16 + Metabase + serveur GeoJSON
  .env                  — credentials locaux (gitignoré)
  init/
    01_schema.sql       — schéma fesi : tables operations, programme_totals, region_metadata
  load_data.py          — charge data/processed/data.json dans PostgreSQL
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
