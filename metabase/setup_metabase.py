"""Provisionne l'instance Metabase : connexion PostgreSQL, carte GeoJSON
métropole, collection `FESI`, page d'accueil et les cinq dashboards **par usage**
(issue #129) — Territoires, Structure & répartition, Pilotage, Analyses &
contrôle, Qualité des sources.

Ces cinq écrans remplacent les cinq dashboards des Phases 1-3 (#121), qui
miroitaient les pages Streamlit une à une : un écran par période, un par
périmètre, un pour comparer deux régions. La réorganisation retenue en #129 fait
de la **période** et du **périmètre** des paramètres et non des écrans, ce qui
fait disparaître le Comparateur en tant que page — un paramètre `Périmètre`
multi-valeurs en fait autant. `archive_legacy()` dissout l'ancien jeu à la fin
du provisionnement, pour qu'une instance déjà provisionnée ne garde pas les
deux côte à côte.

Ce que cette bascule suppose, et qui est verrouillé ailleurs :

- les vues unifiées `v_engage_all` / `v_pilotage_all` (init/05_vues_unifiees.sql),
  dont `verify_vues_unifiees.py` vérifie qu'elles ne rejouent pas le
  double-comptage 2014-2020 de `v_pilotage` et qu'elles couvrent bien les trois
  partitions de la période 2021-2027 ;
- les *field filters* multi-valeurs, qui exigent que Metabase ait synchronisé ces
  vues comme des tables — d'où `sync_views()`, une vue non synchronisée n'ayant
  pas d'id de champ ;
- `verify_dashboards.py`, qui compare chiffre à chiffre ce que rend chaque carte,
  filtres appliqués, à ce qu'affiche Streamlit.

Idempotent : chaque étape cherche la ressource par nom avant de la créer. Mais un
code retour 200 ne prouve rien sur cette API (cf. les gotchas de `move_to_collection`
et de `archive_legacy`) — tout provisionnement est relu après écriture.
"""

import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests requis : venv/bin/pip install requests")

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "dashboard"))

from utils.themes import FONDS_COLORS  # noqa: E402

MB_URL = "http://localhost:3000"
SOURCE_2021_2027 = "2021-2027-conventionnees"
GEOJSON_METROPOLE_URL = (
    "https://raw.githubusercontent.com/benoitdb/cartographie-fesi/main/"
    "frontend/public/geo/regions-metropole.geojson"
)

env = {}
env_path = SCRIPT_DIR / ".env"
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v

FONDS_2021_2027 = ["FEDER", "FSE+", "FTJ"]


def wait_for_health(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{MB_URL}/api/health", timeout=5)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    sys.exit(f"Metabase ne répond pas sur /api/health après {timeout}s")


def get_session():
    props = requests.get(f"{MB_URL}/api/session/properties").json()
    if not props.get("has-user-setup"):
        r = requests.post(
            f"{MB_URL}/api/setup",
            json={
                "token": props["setup-token"],
                "user": {
                    "first_name": "Admin",
                    "last_name": "FESI",
                    "email": env["MB_ADMIN_EMAIL"],
                    "password": env["MB_ADMIN_PASSWORD"],
                },
                "prefs": {"site_name": "FESI", "site_locale": "fr"},
            },
        )
        r.raise_for_status()
        return r.json()["id"]
    r = requests.post(
        f"{MB_URL}/api/session",
        json={"username": env["MB_ADMIN_EMAIL"], "password": env["MB_ADMIN_PASSWORD"]},
    )
    r.raise_for_status()
    return r.json()["id"]


def ensure_database(session):
    dbs = session.get(f"{MB_URL}/api/database").json()
    existing = next((d for d in dbs["data"] if d["name"] == "FESI"), None)
    if existing:
        return existing["id"]
    r = session.post(
        f"{MB_URL}/api/database",
        json={
            "engine": "postgres",
            "name": "FESI",
            "details": {
                "host": "postgres",
                "port": 5432,
                "dbname": env["POSTGRES_DB"],
                "user": env["POSTGRES_USER"],
                "password": env["POSTGRES_PASSWORD"],
                "ssl": False,
            },
            "is_full_sync": True,
        },
    )
    r.raise_for_status()
    db_id = r.json()["id"]
    deadline = time.time() + 60
    while time.time() < deadline:
        status = session.get(f"{MB_URL}/api/database/{db_id}").json()["initial_sync_status"]
        if status == "complete":
            break
        time.sleep(3)
    return db_id


def ensure_geojson_map(session):
    r = session.get(f"{MB_URL}/api/setting/custom-geojson")
    r.raise_for_status()
    maps = r.json()
    if "fesi_metropole" in maps:
        return
    maps["fesi_metropole"] = {
        "name": "Régions métropole (FESI)",
        "url": GEOJSON_METROPOLE_URL,
        "region_key": "nom",
        "region_name": "nom",
        "builtin": False,
    }
    r = session.put(f"{MB_URL}/api/setting/custom-geojson", json={"value": maps})
    r.raise_for_status()


def find_card_by_name(session, name):
    cards = session.get(f"{MB_URL}/api/card").json()
    return next((c for c in cards if c["name"] == name), None)


def upsert_card(session, name, payload):
    existing = find_card_by_name(session, name)
    if existing:
        r = session.put(f"{MB_URL}/api/card/{existing['id']}", json=payload)
        r.raise_for_status()
        return r.json()
    r = session.post(f"{MB_URL}/api/card", json={"name": name, **payload})
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------- Champs et filtres

def table_fields(session, db_id):
    """{nom de table -> {nom de champ -> id}}. Metabase expose les 14 vues `v_*`
    comme des tables ordinaires : leurs colonnes ont donc un id de champ, ce qui
    les rend utilisables comme *field filter* sur une carte SQL native."""
    md = session.get(f"{MB_URL}/api/database/{db_id}/metadata").json()
    return {t["name"]: {f["name"]: f["id"] for f in t["fields"]} for t in md["tables"]}


VUES_UNIFIEES = ("v_engage_all", "v_pilotage_all")


def sync_views(session, db_id, attendues=VUES_UNIFIEES):
    """Metabase ne découvre pas seul une vue créée après la synchronisation
    initiale de la base. `v_engage_all` et `v_pilotage_all`
    (init/05_vues_unifiees.sql) étaient absentes de ses métadonnées, donc sans
    id de champ, donc inutilisables comme field filter — sans la moindre erreur,
    juste des tables introuvables. Un `sync_schema` explicite les fait
    apparaître ; ce script ne le déclenche que si elles manquent."""
    tables = table_fields(session, db_id)
    if all(v in tables for v in attendues):
        return tables
    session.post(f"{MB_URL}/api/database/{db_id}/sync_schema").raise_for_status()
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(3)
        tables = table_fields(session, db_id)
        if all(v in tables for v in attendues):
            return tables
    manquantes = sorted(set(attendues) - set(tables))
    raise RuntimeError(
        f"vues non synchronisées par Metabase : {manquantes} — "
        "vérifier qu'init/05_vues_unifiees.sql a bien été appliqué à PostgreSQL"
    )


def dimension_tag(name, display_name, field_id, tag_id):
    """Field filter (`"type": "dimension"`), et non template-tag texte.

    Un template-tag `"type": "text"` est **mono-valeur** : c'est cette limite qui
    avait imposé deux paramètres `region_a`/`region_b` en Phase 2 pour comparer
    deux régions. Un field filter accepte une liste de valeurs — vérifié sur
    l'instance, `["Bretagne", "Occitanie"]` filtre bien sur les deux. C'est ce
    qui permet au Comparateur de disparaître **en tant qu'écran** (#129) : un
    paramètre `Périmètre` multi-valeurs sur des cartes à dimension périmètre en
    fait autant, sur n'importe quel nombre de régions.

    Non requis, et écrit `WHERE {{tag}}` sans crochets optionnels : sans valeur,
    Metabase substitue une clause toujours vraie. « Aucun filtre » vaut donc
    « tout le périmètre », qui est exactement la sémantique de la vue nationale.
    """
    return {
        name: {
            "id": tag_id,
            "name": name,
            "display-name": display_name,
            "type": "dimension",
            "dimension": ["field", field_id, None],
            "widget-type": "string/=",
            "required": False,
        }
    }
COLLECTION_NAME = "FESI"
COLLECTION_DESCRIPTION = (
    "Tableaux de bord des fonds européens structurels et d'investissement. "
    "Sans cette collection, tout atterrit à la racine, mêlé au contenu d'exemple "
    "livré avec Metabase (issue #129)."
)


def ensure_collection(session):
    """Collection dédiée : les dashboards des Phases 1-3 avaient `collection_id`
    à NULL, donc posés à la racine à côté du `E-commerce Insights` d'exemple.
    C'est la cause du « éparpillé » constaté à l'usage, pas une limite de l'outil."""
    collections = session.get(f"{MB_URL}/api/collection").json()
    existing = next((c for c in collections if c["name"] == COLLECTION_NAME), None)
    if existing:
        return existing["id"]
    r = session.post(
        f"{MB_URL}/api/collection",
        json={"name": COLLECTION_NAME, "description": COLLECTION_DESCRIPTION},
    )
    r.raise_for_status()
    return r.json()["id"]


def move_to_collection(session, collection_id, dashboard_ids, card_ids):
    """Range dashboards et cartes dans la collection. Idempotent.

    Deux pièges d'API rencontrés ici (v0.63.16), à ne pas réapprendre :

    - `PUT /api/card/:id` avec le seul `collection_id` répond **400** ; le
      déplacement passe par `POST /api/card/collections`, qui prend une liste.
    - la liste `GET /api/card` renvoie `dataset_query` en forme MBQL normalisée
      (`{"stages": [...]}`), pas la forme legacy `{"type": "native", ...}` —
      reconnaître une carte en reniflant son SQL depuis cette liste ne marche
      donc pas. On passe les identifiants que le script vient de créer, ce qui
      est de toute façon plus sûr que de deviner.
    """
    for dash_id in dashboard_ids:
        r = session.put(f"{MB_URL}/api/dashboard/{dash_id}", json={"collection_id": collection_id})
        r.raise_for_status()
    if card_ids:
        r = session.post(
            f"{MB_URL}/api/card/collections",
            json={"card_ids": sorted(card_ids), "collection_id": collection_id},
        )
        r.raise_for_status()


ACCUEIL_NAME = "FESI — Accueil"


def ensure_accueil_dashboard(session, collection_id, liens):
    """Page de garde : Metabase n'a pas de navigation multipage comme Streamlit.
    Des cartes `link` vers chaque dashboard, posées en page d'accueil de
    l'instance, en tiennent lieu."""
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == ACCUEIL_NAME), None)
    dash_id = existing["id"] if existing else session.post(
        f"{MB_URL}/api/dashboard",
        json={"name": ACCUEIL_NAME, "collection_id": collection_id},
    ).json()["id"]

    dashcards = [
        {
            "id": -1,
            "card_id": None,
            "row": 0,
            "col": 0,
            "size_x": 24,
            "size_y": 2,
            "visualization_settings": {
                "virtual_card": {
                    "display": "text",
                    "archived": False,
                    "dataset_query": {},
                    "visualization_settings": {},
                },
                "text": (
                    "# Fonds européens structurels et d'investissement\n"
                    "Montants **engagés** (opérations conventionnées) et **programmés** "
                    "(Accord de partenariat). Un taux de consommation reste une estimation : "
                    "les enveloppes 2021-2027 viennent de la version préliminaire de juin 2022."
                ),
            },
        }
    ]
    for i, (titre, cible_id, description) in enumerate(liens):
        dashcards.append({
            "id": -(i + 2),
            "card_id": None,
            "row": 2 + (i // 2) * 2,
            "col": (i % 2) * 12,
            "size_x": 12,
            "size_y": 2,
            "visualization_settings": {
                "virtual_card": {
                    "display": "link",
                    "archived": False,
                    "dataset_query": {},
                    "visualization_settings": {},
                },
                "link": {
                    "entity": {
                        "id": cible_id,
                        "model": "dashboard",
                        "name": titre,
                        "description": description,
                        "display": "dashboard",
                    }
                },
            },
        })

    r = session.put(f"{MB_URL}/api/dashboard/{dash_id}", json={"dashcards": dashcards})
    r.raise_for_status()
    return dash_id


def ensure_custom_homepage(session, dash_id):
    """Sans ça, l'instance ouvre sur la page d'accueil générique de Metabase et
    les dashboards restent à chercher."""
    session.put(f"{MB_URL}/api/setting/custom-homepage", json={"value": True})
    r = session.put(f"{MB_URL}/api/setting/custom-homepage-dashboard", json={"value": dash_id})
    r.raise_for_status()


# --------------------------------------------------------- Cartes unifiées (#129)

# Un identifiant de paramètre par dimension, partagé par TOUS les dashboards par
# usage : c'est ce qui rend les cartes interchangeables d'un écran à l'autre.
PARAM_PERIODE = "fesi-periode"
PARAM_PERIMETRE = "fesi-perimetre"
PARAM_FONDS = "fesi-fonds"

PERIODE_PAR_DEFAUT = "2021-2027"

# Les tags portés par chaque carte, pour ne câbler que les paramètres qu'elle
# comprend. Un `parameter_mapping` vers un tag inexistant est accepté par l'API
# (200) et simplement ignoré à l'exécution : le filtre semble posé et ne filtre
# rien. Cette table est la seule source de vérité du câblage.
CARD_TAGS = {
    "engage_montant": ("periode", "perimetre", "fonds"),
    "engage_n_operations": ("periode", "perimetre", "fonds"),
    "engage_par_fonds": ("periode", "perimetre", "fonds"),
    "engage_par_perimetre": ("periode", "perimetre", "fonds"),
    "engage_carte": ("periode", "fonds"),
    "pilotage_par_fonds": ("periode", "perimetre", "fonds"),
    "pilotage_taux_perimetre": ("periode", "fonds"),
    "pilotage_detail": ("periode", "perimetre", "fonds"),
    "pilotage_trajectoire": ("fonds",),
    "controle_cofinancement": ("perimetre",),
    "sources_chargement": ("periode",),
}

SERIES_FONDS = {f: {"color": c} for f, c in FONDS_COLORS.items()}

# Périmètres non géographiques de `v_engage_all` : le volet national et
# l'interrégional sont des partitions à part entière (cf. init/02_views.sql et
# la troisième branche de v_engage_all), qu'aucune carte choroplèthe ne peut
# placer sur un fond de carte régional.
PERIMETRES_HORS_CARTE = "('national', 'interregional')"


def build_usage_cards(session, db_id, tables):
    """Les 11 cartes des dashboards par usage, qui remplacent les 21 cartes des
    Phases 1-3.

    Le compte baisse parce que les 21 disaient largement la même chose sur des
    périmètres différents, chacune avec sa propre convention de paramètre :
    `fonds` seul pour le national, `region` pour le régional, `region_a`/`region_b`
    pour le comparateur, aucun tag pour le volet national, `perimetre` pour
    2014-2020. La période et le périmètre devenant des **paramètres** et non des
    écrans (#129), une seule carte par mesure suffit.

    Toutes s'appuient sur les vues unifiées `v_engage_all` / `v_pilotage_all`,
    dont la justesse par période est verrouillée par `verify_vues_unifiees.py` —
    et notamment l'absence du double-comptage 2014-2020 de `v_pilotage`.
    """
    engage = tables["v_engage_all"]
    pilotage = tables["v_pilotage_all"]
    ops = tables["operations"]
    cofi = tables["v_cofinancement_2014_2020_summary"]
    tag_id = "b1000000-0000-0000-0000-0000000000%02d"

    def filtres(champs, table, depart=0):
        """Les trois field filters standards, sur les champs d'une même table."""
        libelles = {"periode": "Période", "perimetre": "Périmètre", "fonds": "Fonds"}
        tags = {}
        for i, nom in enumerate(champs):
            tags.update(dimension_tag(nom, libelles[nom], table[nom], tag_id % (depart + i)))
        return tags

    cards = {}

    cards["engage_montant"] = upsert_card(
        session,
        "Engagé — Montant UE",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT SUM(engage) AS montant_ue FROM v_engage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}}"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), engage, 10),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["engage_n_operations"] = upsert_card(
        session,
        "Engagé — Nombre d'opérations",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT SUM(n_operations) AS n_operations FROM v_engage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}}"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), engage, 20),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["engage_par_fonds"] = upsert_card(
        session,
        "Engagé — Par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, SUM(engage) AS montant_ue FROM v_engage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY fonds ORDER BY fonds"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), engage, 30),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["fonds"],
                "graph.metrics": ["montant_ue"],
                "series_settings": SERIES_FONDS,
            },
        },
    )

    cards["engage_par_perimetre"] = upsert_card(
        session,
        "Engagé — Par périmètre",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # C'est cette carte qui remplace l'écran Comparateur : sans
                    # filtre elle classe les 20 périmètres, avec deux valeurs de
                    # `Périmètre` elle en met deux côte à côte. Aucune carte
                    # dédiée à la comparaison n'est nécessaire.
                    "query": (
                        "SELECT perimetre, SUM(engage) AS montant_ue, "
                        "SUM(n_operations) AS n_operations FROM v_engage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY perimetre ORDER BY 2 DESC"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), engage, 40),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["perimetre"],
                "graph.metrics": ["montant_ue"],
            },
        },
    )

    cards["engage_carte"] = upsert_card(
        session,
        "Engagé — Carte des régions",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Pas de filtre `Périmètre` sur cette carte : une choroplèthe
                    # filtrée sur une région n'affiche qu'une tache isolée sur un
                    # fond vide. Elle reste la vue d'ensemble, et le zoom se fait
                    # par les cartes voisines. `national`/`interregional` sont
                    # écartés explicitement plutôt que laissés au fond de carte,
                    # qui les ignorerait en silence.
                    "query": (
                        "SELECT perimetre AS region, SUM(engage) AS montant_ue "
                        "FROM v_engage_all "
                        f"WHERE perimetre NOT IN {PERIMETRES_HORS_CARTE} "
                        "AND {{periode}} AND {{fonds}} "
                        "GROUP BY perimetre ORDER BY perimetre"
                    ),
                    "template-tags": filtres(("periode", "fonds"), engage, 50),
                },
                "database": db_id,
            },
            "display": "map",
            "visualization_settings": {
                "map.type": "region",
                "map.region": "fesi_metropole",
                "map.metric_column": "montant_ue",
                "map.dimension_column": "region",
            },
        },
    )

    cards["pilotage_par_fonds"] = upsert_card(
        session,
        "Pilotage — Programmé vs engagé par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # `taux` et `reste_a_engager` sont recalculés après agrégation
                    # et jamais sommés : les deux formules ne sont pas linéaires
                    # (#62 — taux non plafonné, reste à engager planché à 0 PAR
                    # FONDS). Sur un périmètre unique le GROUP BY ne laisse qu'une
                    # ligne par fonds et le résultat est identique à la lecture
                    # directe de la vue ; sur plusieurs, il somme d'abord.
                    "query": (
                        "SELECT fonds, SUM(programme) AS programme, SUM(engage) AS engage, "
                        "CASE WHEN SUM(programme) > 0 THEN SUM(engage) / SUM(programme) "
                        "ELSE 0 END AS taux, "
                        "GREATEST(SUM(programme) - SUM(engage), 0) AS reste_a_engager "
                        "FROM v_pilotage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY fonds ORDER BY fonds"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), pilotage, 60),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["fonds"],
                "graph.metrics": ["programme", "engage"],
            },
        },
    )

    cards["pilotage_taux_perimetre"] = upsert_card(
        session,
        "Pilotage — Taux de consommation par périmètre",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT perimetre, "
                        "CASE WHEN SUM(programme) > 0 THEN SUM(engage) / SUM(programme) "
                        "ELSE 0 END AS taux "
                        "FROM v_pilotage_all "
                        "WHERE {{periode}} AND {{fonds}} "
                        "GROUP BY perimetre ORDER BY 2 DESC"
                    ),
                    "template-tags": filtres(("periode", "fonds"), pilotage, 70),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["perimetre"],
                "graph.metrics": ["taux"],
            },
        },
    )

    cards["pilotage_detail"] = upsert_card(
        session,
        "Pilotage — Détail par périmètre et fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Lecture directe, sans agrégation : à la maille (périmètre,
                    # fonds) la vue porte déjà taux et reste à engager avec la
                    # bonne formule, il n'y a rien à recalculer.
                    "query": (
                        "SELECT periode, perimetre, fonds, programme, engage, taux, "
                        "reste_a_engager FROM v_pilotage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "ORDER BY periode, perimetre, fonds"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), pilotage, 80),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {},
        },
    )

    cards["pilotage_trajectoire"] = upsert_card(
        session,
        "Pilotage — Engagement cumulé 2021-2027",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Seule carte qui reste scopée à une période en dur, et son
                    # titre le dit. Une trajectoire 2014-2020 demanderait des
                    # dates par opération sur le périmètre FUSIONNÉ des six
                    # sources ; `v_perimetre_2014_2020` ne porte pas de date, et
                    # cumuler sur `operations` pour cette période rejouerait le
                    # double-comptage de #68/#95. À traiter en Phase C, pas ici.
                    #
                    # `date_debut`, pas `date_convention` (arbitrage Phase 4,
                    # #121) : c'est la date qu'utilise `build_trajectoire` côté
                    # Streamlit. L'écart entre les deux courbes avait été chiffré
                    # à 2 324 M€ sur le dernier point.
                    "query": (
                        "SELECT mois, SUM(montant_mois) OVER (ORDER BY mois) AS montant_cumule "
                        "FROM (SELECT date_trunc('month', date_debut) AS mois, "
                        "SUM(montant_ue) AS montant_mois FROM operations "
                        f"WHERE source_id = '{SOURCE_2021_2027}' AND date_debut IS NOT NULL "
                        "AND {{fonds}} GROUP BY 1) t ORDER BY mois"
                    ),
                    "template-tags": filtres(("fonds",), ops, 90),
                },
                "database": db_id,
            },
            "display": "line",
            "visualization_settings": {},
        },
    )

    cards["controle_cofinancement"] = upsert_card(
        session,
        "Contrôle — Dépassements de plafond de cofinancement (2014-2020)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Pas de filtre de période : un plafond de cofinancement au
                    # sens de l'art. 120 du règlement 1303/2013 est une notion
                    # 2014-2020, adossée aux catégories de cohésion de cette
                    # période. Le filtre `Périmètre` porte ici sur `region`, seul
                    # maillage où un plafond est opposable — un agrégat national
                    # n'en a pas.
                    "query": (
                        "SELECT region, fonds, categorie_ue, plafond_min, plafond_max, "
                        "n_operations, n_depassements, montant_depassements, "
                        "n_taux_divergents, montant_taux_divergents "
                        "FROM v_cofinancement_2014_2020_summary "
                        "WHERE {{perimetre}} ORDER BY region, fonds"
                    ),
                    "template-tags": dimension_tag(
                        "perimetre", "Périmètre", cofi["region"], tag_id % 95
                    ),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {},
        },
    )

    cards["sources_chargement"] = upsert_card(
        session,
        "Sources — Opérations chargées par source",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Les six sources 2014-2020 se chevauchent (substitution
                    # Bretagne/Normandie/Nouvelle-Aquitaine, addition PON FSE) :
                    # ce tableau compte ce qui est CHARGÉ, source par source, et
                    # ne doit jamais être sommé pour obtenir un total de période.
                    # C'est précisément ce que font les vues `v_*_2014_2020`.
                    "query": (
                        "SELECT source_id, periode, COUNT(*) AS n_operations, "
                        "SUM(montant_ue) AS montant_ue, "
                        "COUNT(*) FILTER (WHERE fonds IS NULL) AS sans_fonds, "
                        "COUNT(*) FILTER (WHERE region IS NULL) AS sans_region "
                        "FROM operations WHERE {{periode}} "
                        "GROUP BY source_id, periode ORDER BY periode, source_id"
                    ),
                    "template-tags": filtres(("periode",), ops, 98),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {},
        },
    )

    return cards


# --------------------------------------------- Dashboards par usage (#129, phase A)

def _virtual_dashcard(dashcard_id, tab_id, display, texte, row, col, size_x, size_y):
    """Carte virtuelle `heading` ou `text` : l'équivalent Metabase de
    `st.subheader` et `st.markdown`. Sans elles, un dashboard n'est qu'une grille
    de graphiques sans énoncé — or la moitié de ce que dit le dashboard Streamlit
    tient dans ses captions (réserves de méthode, périmètres, sources)."""
    return {
        "id": dashcard_id,
        "card_id": None,
        "dashboard_tab_id": tab_id,
        "row": row,
        "col": col,
        "size_x": size_x,
        "size_y": size_y,
        "visualization_settings": {
            "virtual_card": {
                "display": display,
                "archived": False,
                "dataset_query": {},
                "visualization_settings": {},
            },
            "text": texte,
        },
    }


PARAM_IDS = {"periode": PARAM_PERIODE, "perimetre": PARAM_PERIMETRE, "fonds": PARAM_FONDS}


def ensure_usage_dashboard(session, collection_id, nom, description, dimensions, onglets, cards):
    """Un dashboard « par usage » : des onglets, et les mêmes paramètres partagés
    sur tous.

    `onglets` est une liste de (nom, [éléments]), où un élément vaut
    ("card", clé, row, col, size_x, size_y) ou ("heading"|"text", markdown,
    row, col, size_x, size_y). Le layout est déclaratif depuis la Phase 1
    (grille 24 colonnes) : rien ne se place à la souris, mais rien non plus ne
    se vérifie par l'API — le rendu est client-side, seul l'oeil le voit.
    """
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == nom), None)
    dash_id = existing["id"] if existing else session.post(
        f"{MB_URL}/api/dashboard",
        json={"name": nom, "description": description, "collection_id": collection_id},
    ).json()["id"]

    tabs = [{"id": -(i + 1), "name": titre, "position": i} for i, (titre, _) in enumerate(onglets)]
    dashcards = []
    compteur = 0
    for (_, elements), tab in zip(onglets, tabs, strict=True):
        for element in elements:
            compteur += 1
            genre, contenu, row, col, size_x, size_y = element
            if genre != "card":
                dashcards.append(_virtual_dashcard(
                    -compteur, tab["id"], genre, contenu, row, col, size_x, size_y
                ))
                continue
            card = cards[contenu]
            dashcards.append({
                "id": -compteur,
                "card_id": card["id"],
                "dashboard_tab_id": tab["id"],
                "row": row,
                "col": col,
                "size_x": size_x,
                "size_y": size_y,
                # Câblage restreint aux tags que la carte porte réellement
                # (CARD_TAGS) : un mapping vers un tag absent est accepté en 200
                # et ignoré à l'exécution — le filtre paraît branché et ne filtre
                # rien. Même famille de défaut silencieux que le `display` non
                # validé et que `PUT /api/card/:id` sur le seul `collection_id`.
                "parameter_mappings": [
                    {
                        "parameter_id": PARAM_IDS[tag],
                        "card_id": card["id"],
                        "target": ["dimension", ["template-tag", tag]],
                    }
                    for tag in CARD_TAGS[contenu]
                    if tag in dimensions
                ],
            })

    libelles = {"periode": "Période", "perimetre": "Périmètre", "fonds": "Fonds"}
    parameters = []
    for tag in dimensions:
        param = {
            "id": PARAM_IDS[tag],
            "name": libelles[tag],
            "slug": tag,
            "type": "string/=",
        }
        if tag == "periode":
            # Sans valeur par défaut, les cartes somment les deux périodes dans
            # un même chiffre (28 349 M€ mesurés, qui ne veulent rien dire :
            # 2014-2020 est close, 2021-2027 en cours). La période reste un
            # paramètre — c'est tout l'objet de la réorganisation — mais elle
            # part sur la période de référence du projet.
            param["default"] = [PERIODE_PAR_DEFAUT]
        parameters.append(param)

    r = session.put(
        f"{MB_URL}/api/dashboard/{dash_id}",
        json={
            "description": description,
            "parameters": parameters,
            "tabs": tabs,
            "dashcards": dashcards,
        },
    )
    r.raise_for_status()
    return dash_id


A_VENIR = (
    "### À construire\n"
    "Cet onglet fait partie de la charpente posée en phase A (#129) ; son contenu "
    "arrive avec la phase indiquée ci-dessous. Il est laissé visible plutôt que "
    "masqué : la navigation cible se juge entière, pas par morceaux.\n\n"
)

TERRITOIRES_NAME = "FESI — Territoires"
STRUCTURE_NAME = "FESI — Structure & répartition"
PILOTAGE_NAME = "FESI — Pilotage"
ANALYSES_NAME = "FESI — Analyses & contrôle"
QUALITE_NAME = "FESI — Qualité des sources"

NOTE_PERIMETRE = (
    "Le filtre **Périmètre** accepte **plusieurs valeurs** : une région, "
    "plusieurs, `national` (programmes nationaux) ou `interregional`. C'est ce "
    "qui remplace l'ancien écran Comparateur — comparer deux régions revient à "
    "en cocher deux."
)


def ensure_usage_dashboards(session, collection_id, cards):
    """Les cinq dashboards par usage, dans l'ordre où la page d'accueil les
    présente. Chacun rend une question, pas une page Streamlit : la période et
    le périmètre y sont des paramètres, plus des écrans."""
    dash = {}

    dash[TERRITOIRES_NAME] = ensure_usage_dashboard(
        session, collection_id, TERRITOIRES_NAME,
        "Où va l'argent : carte, classement des périmètres, détail d'un périmètre.",
        ("periode", "perimetre", "fonds"),
        [
            ("Vue nationale", [
                ("heading", "Répartition géographique", 0, 0, 24, 1),
                ("card", "engage_carte", 1, 0, 16, 8),
                ("card", "engage_montant", 1, 16, 8, 4),
                ("card", "engage_n_operations", 5, 16, 8, 4),
                ("card", "engage_par_perimetre", 9, 0, 24, 6),
                ("text",
                 "La choroplèthe ne porte que les régions métropolitaines : les "
                 "DROM-COM y seraient invisibles à cette échelle (encarts dédiés, "
                 "phase E). `national` et `interregional` sont écartés de la carte "
                 "mais présents dans le classement ci-dessus.",
                 15, 0, 24, 2),
            ]),
            ("Détail périmètre", [
                ("text", NOTE_PERIMETRE, 0, 0, 24, 2),
                ("card", "engage_montant", 2, 0, 8, 4),
                ("card", "engage_n_operations", 2, 8, 8, 4),
                ("card", "engage_par_fonds", 2, 16, 8, 8),
                ("card", "pilotage_detail", 6, 0, 16, 6),
            ]),
            ("Rattachements atypiques", [
                ("text", A_VENIR + "Opérations dont le rattachement régional diverge "
                 "entre le fichier source et la région moderne, et opérations "
                 "interrégionales. **Phase E.**", 0, 0, 24, 3),
            ]),
        ],
        cards,
    )

    dash[STRUCTURE_NAME] = ensure_usage_dashboard(
        session, collection_id, STRUCTURE_NAME,
        "Comment se répartit l'enveloppe : par fonds, par hiérarchie thématique, par programme.",
        ("periode", "perimetre", "fonds"),
        [
            ("Fonds", [
                ("heading", "Répartition par fonds", 0, 0, 24, 1),
                ("card", "engage_par_fonds", 1, 0, 16, 7),
                ("card", "engage_montant", 1, 16, 8, 4),
                ("card", "engage_n_operations", 5, 16, 8, 3),
                ("text",
                 "Les libellés de fonds diffèrent d'une période à l'autre : "
                 "FEDER/FSE+/FTJ en 2021-2027, FEDER/FEDER REACT-EU/FSE/IEJ en "
                 "2014-2020. Un même graphique montre donc des séries différentes "
                 "selon la période choisie — ce n'est pas une anomalie.",
                 8, 0, 24, 2),
            ]),
            ("Hiérarchie", [
                ("text", A_VENIR + "Treemap fonds → objectif stratégique → objectif "
                 "spécifique, et répartition par domaine d'intervention (2014-2020). "
                 "**Phase C.**", 0, 0, 24, 3),
            ]),
            ("Programmes", [
                ("text", A_VENIR + "Portefeuille de programmes : nuage de points "
                 "montant/nombre d'opérations, montant par habitant, classement. "
                 "**Phase C.**", 0, 0, 24, 3),
            ]),
        ],
        cards,
    )

    dash[PILOTAGE_NAME] = ensure_usage_dashboard(
        session, collection_id, PILOTAGE_NAME,
        "Où en est la consommation : programmé vs engagé, trajectoire, comparaison entre périmètres.",
        ("periode", "perimetre", "fonds"),
        [
            ("Synthèse", [
                ("heading", "Programmé vs engagé", 0, 0, 24, 1),
                ("card", "pilotage_par_fonds", 1, 0, 24, 7),
                ("card", "pilotage_detail", 8, 0, 24, 7),
                ("text",
                 "Un taux de consommation reste une **estimation** : les enveloppes "
                 "2021-2027 viennent de la version préliminaire de juin 2022 de "
                 "l'Accord de partenariat. Le taux n'est jamais plafonné et le reste "
                 "à engager est calculé par fonds puis planché à 0 (#62).",
                 15, 0, 24, 2),
            ]),
            ("Trajectoire", [
                ("card", "pilotage_trajectoire", 0, 0, 24, 8),
                ("text",
                 "**Cette courbe ignore le filtre Période** : elle est scopée à "
                 "2021-2027 en dur, et son titre le dit. Une trajectoire 2014-2020 "
                 "demanderait des dates par opération sur le périmètre fusionné des "
                 "six sources — cumuler directement sur `operations` rejouerait le "
                 "double-comptage de #68/#95. Phase C.",
                 8, 0, 24, 3),
            ]),
            ("Comparaison régionale", [
                ("text", NOTE_PERIMETRE + "\n\nLe classement ci-dessous ignore "
                 "volontairement ce filtre : il sert à situer un périmètre parmi "
                 "tous les autres.", 0, 0, 24, 3),
                ("card", "pilotage_taux_perimetre", 3, 0, 24, 8),
            ]),
        ],
        cards,
    )

    dash[ANALYSES_NAME] = ensure_usage_dashboard(
        session, collection_id, ANALYSES_NAME,
        "Ce que la moyenne cache : distribution, concentration, cofinancement, cohérence des sources.",
        ("periode", "perimetre", "fonds"),
        [
            ("Distribution", [
                ("text", A_VENIR + "Histogrammes des montants, boîtes à moustaches "
                 "par fonds et par région, statistiques descriptives, opérations "
                 "atypiques au sens de l'écart interquartile. **Phase D.**",
                 0, 0, 24, 3),
            ]),
            ("Concentration", [
                ("text", A_VENIR + "Courbe de Pareto et courbe de Lorenz sur les "
                 "montants par bénéficiaire et par opération. **Phase D.**",
                 0, 0, 24, 3),
            ]),
            ("Cofinancement", [
                ("heading", "Taux de cofinancement face au plafond réglementaire", 0, 0, 24, 1),
                ("card", "controle_cofinancement", 1, 0, 24, 8),
                ("text",
                 "**2014-2020 uniquement**, quelle que soit la Période choisie : le "
                 "plafond de l'art. 120 du règlement 1303/2013 s'adosse aux "
                 "catégories de cohésion de cette période. Le filtre Périmètre porte "
                 "ici sur la région, seule maille où un plafond est opposable.\n\n"
                 "`n_taux_divergents` n'est pas un second dépassement : c'est le "
                 "nombre d'opérations dont le taux déclaré par le fichier source "
                 "s'écarte de plus d'un point du taux recalculé, qui seul fait foi "
                 "(#127).",
                 9, 0, 24, 3),
            ]),
            ("Cohérence", [
                ("text", A_VENIR + "Rapprochement opérations / enveloppes "
                 "programmées, et écarts entre sources sur un même périmètre. "
                 "**Phase D.**", 0, 0, 24, 3),
            ]),
        ],
        cards,
    )

    dash[QUALITE_NAME] = ensure_usage_dashboard(
        session, collection_id, QUALITE_NAME,
        "D'où viennent les chiffres : sources chargées, complétude des champs.",
        ("periode",),
        [
            ("Sources", [
                ("heading", "Ce qui est chargé, source par source", 0, 0, 24, 1),
                ("card", "sources_chargement", 1, 0, 24, 7),
                ("text",
                 "**Ces lignes ne se somment pas.** Les six sources 2014-2020 se "
                 "chevauchent : Bretagne, Normandie et Nouvelle-Aquitaine ont leur "
                 "propre fichier ET des opérations dans Synergie (substitution), et "
                 "le PON FSE se fusionne par opération dans les régions ou le "
                 "national (addition). C'est `v_perimetre_2014_2020` qui résout ces "
                 "règles — jamais une somme de ce tableau.\n\n"
                 "`sans_fonds` et `sans_region` comptent les champs non renseignés à "
                 "la source, pas des erreurs de chargement.",
                 8, 0, 24, 4),
            ]),
            ("Complétude", [
                ("text", A_VENIR + "Taux de remplissage champ par champ et source "
                 "par source, et contrôles de cohérence de `4_Validation_source`. "
                 "**Phase E.**", 0, 0, 24, 3),
            ]),
        ],
        cards,
    )

    return dash


# ------------------------------------------- Dissolution des écrans des Phases 1-3

# Les cinq dashboards et vingt-et-une cartes des Phases 1-3, dissous par la
# réorganisation par usage (#129). Archivés et non supprimés : l'archivage est
# réversible depuis l'interface, et un dashboard effacé emporterait avec lui
# d'éventuels favoris ou abonnements. Ils restent listés ici nommément pour que
# le script reste idempotent — sans ça, une instance déjà provisionnée garderait
# les deux jeux d'écrans côte à côte, ce qui est précisément l'« éparpillé »
# que ce chantier corrige.
DASHBOARDS_DISSOUS = [
    "FESI — Vue nationale 2021-2027",
    "FESI — Vue régionale 2021-2027",
    "FESI — Comparateur régions 2021-2027",
    "FESI — Volet national 2021-2027",
    "FESI — Période 2014-2020",
]

CARTES_DISSOUTES = [
    "Nombre d'opérations",
    "Montant UE total",
    "Montant UE par fonds",
    "Engagement cumulé",
    "Montant UE par région",
    "Région — Montant UE total",
    "Région — Nombre d'opérations",
    "Région — Montant UE par fonds",
    "Région — Programmé vs engagé par fonds",
    "Comparateur — Montant UE par fonds",
    "Comparateur — Taux de consommation par fonds",
    "Comparateur — KPI par région",
    "Volet national — Montant UE total",
    "Volet national — Nombre d'opérations",
    "Volet national — Montant UE par fonds",
    "Volet national — Programmé vs engagé par fonds",
    "2014-2020 — Montant programmé total",
    "2014-2020 — Nombre d'opérations",
    "2014-2020 — Montant programmé par fonds",
    "2014-2020 — Programmé vs engagé par fonds",
    "2014-2020 — Dépassements de plafond de cofinancement",
]


def archive_legacy(session):
    """Archive les écrans des Phases 1-3 et leurs cartes. Relu depuis l'API
    après écriture, comme tout provisionnement Metabase ici : un 200 n'est pas
    une preuve que quelque chose a bougé (cf. `move_to_collection`)."""
    dashboards = {d["name"]: d for d in session.get(f"{MB_URL}/api/dashboard").json()}
    archives = 0
    for nom in DASHBOARDS_DISSOUS:
        d = dashboards.get(nom)
        if not d or d.get("archived"):
            continue
        r = session.put(f"{MB_URL}/api/dashboard/{d['id']}", json={"archived": True})
        r.raise_for_status()
        archives += 1

    cartes = {c["name"]: c for c in session.get(f"{MB_URL}/api/card").json()}
    ids = [cartes[n]["id"] for n in CARTES_DISSOUTES if n in cartes and not cartes[n].get("archived")]
    for card_id in ids:
        r = session.put(f"{MB_URL}/api/card/{card_id}", json={"archived": True})
        r.raise_for_status()

    restants = [
        c["name"]
        for c in session.get(f"{MB_URL}/api/card").json()
        if c["name"] in CARTES_DISSOUTES and not c.get("archived")
    ]
    if restants:
        raise RuntimeError(f"cartes non archivées malgré un 200 : {restants}")
    return archives, len(ids)


def main():
    wait_for_health()
    token = get_session()
    session = requests.Session()
    session.headers["X-Metabase-Session"] = token

    db_id = ensure_database(session)
    ensure_geojson_map(session)
    tables = sync_views(session, db_id)

    collection_id = ensure_collection(session)
    cards = build_usage_cards(session, db_id, tables)
    move_to_collection(session, collection_id, [], [c["id"] for c in cards.values()])

    dash = ensure_usage_dashboards(session, collection_id, cards)
    for nom, dash_id in dash.items():
        print(f"{nom} : {MB_URL}/dashboard/{dash_id}")

    liens = [
        (TERRITOIRES_NAME, dash[TERRITOIRES_NAME],
         "Où va l'argent : carte, classement des périmètres, détail d'un périmètre."),
        (STRUCTURE_NAME, dash[STRUCTURE_NAME],
         "Comment se répartit l'enveloppe : par fonds, par thématique, par programme."),
        (PILOTAGE_NAME, dash[PILOTAGE_NAME],
         "Où en est la consommation : programmé vs engagé, trajectoire, comparaison."),
        (ANALYSES_NAME, dash[ANALYSES_NAME],
         "Ce que la moyenne cache : distribution, concentration, cofinancement."),
        (QUALITE_NAME, dash[QUALITE_NAME],
         "D'où viennent les chiffres : sources chargées, complétude des champs."),
    ]
    accueil_id = ensure_accueil_dashboard(session, collection_id, liens)
    ensure_custom_homepage(session, accueil_id)
    print(f"Accueil : {MB_URL}/dashboard/{accueil_id}")

    n_dash, n_cards = archive_legacy(session)
    print(f"Écrans des Phases 1-3 dissous : {n_dash} dashboard(s), {n_cards} carte(s) archivés")


if __name__ == "__main__":
    main()
