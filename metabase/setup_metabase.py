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
# Seule source 2014-2020 à porter `date_programmation` (100 % renseignée ;
# 0 % sur les cinq autres). C'est ce qui borne la trajectoire de la période —
# voir la carte `pilotage_trajectoire_2014_2020`.
SOURCE_SYNERGIE_2014_2020 = "2014-2020-synergie"
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


# Toute vue servant de field filter doit être synchronisée : sans id de champ,
# le filtre est inconstructible. `v_repartition_all` (phase B) et
# `allocations_rup` s'y ajoutent avec la phase C.
VUES_UNIFIEES = (
    "v_engage_all",
    "v_pilotage_all",
    "v_repartition_all",
    "allocations_rup",
)


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

    **La table visée par un field filter ne doit JAMAIS être aliasée dans la
    requête.** Metabase substitue une clause qualifiée du nom réel de la table
    (`"public"."v_engage_all"."perimetre" IN (…)`) ; un `FROM v_engage_all e`
    rend cette référence invalide et PostgreSQL répond
    « invalid reference to FROM-clause entry ». Les tables *jointes* peuvent
    garder leur alias — seule celle du filtre est contrainte.

    Le piège est que **la faute ne se voit pas sans valeur** : le filtre vide se
    réduit à une clause triviale, la requête passe, la carte affiche ses lignes.
    Elle ne casse qu'au premier clic de l'utilisateur. Tout contrôle de relecture
    doit donc exercer les filtres AVEC une valeur — même famille de défaut
    silencieux que le `display` non validé et le `parameter_mapping` orphelin.
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
    "pilotage_trajectoire_2014_2020": ("fonds",),
    "structure_treemap": ("periode", "perimetre", "fonds"),
    "structure_portefeuille": ("periode", "perimetre", "fonds"),
    "structure_par_habitant": ("periode", "perimetre", "fonds"),
    "structure_rup": ("perimetre", "fonds"),
    "controle_cofinancement": ("perimetre",),
    "sources_chargement": ("periode",),
    # Phase D — Analyses & contrôle. Le tag `perimetre` de ces cartes pointe
    # sur `operations.region` (pas `v_engage_all.perimetre`) : les périmètres
    # 'national'/'interregional' (region NULL ou flag sans valeur) ne matchent
    # pas, et la carte est vide — comportement voulu, voir le commentaire de
    # build_usage_cards Phase D.
    "analyse_stats_fonds": ("periode", "perimetre", "fonds"),
    "analyse_histogramme": ("periode", "perimetre", "fonds"),
    "analyse_boxplot_stats": ("periode", "perimetre", "fonds"),
    "analyse_outliers": ("periode", "perimetre", "fonds"),
    "analyse_top_beneficiaires": ("periode", "perimetre", "fonds"),
    "analyse_lorenz": ("periode", "perimetre", "fonds"),
    "analyse_coherence": ("periode", "perimetre", "fonds"),
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
    repartition = tables["v_repartition_all"]
    rup = tables["allocations_rup"]
    tag_id = "b1000000-0000-0000-0000-0000000000%02d"
    # Les décades 10 à 98 du radical ci-dessus sont prises par les phases A/B.
    # La phase C prend son propre radical plutôt que de se glisser dans les
    # trous : deux tags qui partagent un id se recouvrent en silence.
    tag_id_c = "b1000000-0000-0000-0000-0000000001%02d"

    def filtres(champs, table, depart=0, radical=None, colonnes=None):
        """Les trois field filters standards, sur les champs d'une même table.

        colonnes (optionnel, dict) : renomme un champ de tag vers la colonne
        réelle de la table. Ex. ``{"perimetre": "region"}`` crée un tag nommé
        ``perimetre`` (câblé au paramètre dashboard ``fesi-perimetre``) mais
        pointé sur ``table["region"]`` — nécessaire quand la table cible n'a
        pas de colonne ``perimetre`` (cas d'``operations``, dont le périmètre
        est porté par ``region``)."""
        libelles = {"periode": "Période", "perimetre": "Périmètre", "fonds": "Fonds"}
        colonnes = colonnes or {}
        radical = radical or tag_id
        tags = {}
        for i, nom in enumerate(champs):
            col = colonnes.get(nom, nom)
            tags.update(dimension_tag(nom, libelles[nom], table[col], radical % (depart + i)))
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

    # ------------------------------------------------- Phase C : Structure & Pilotage

    cards["structure_treemap"] = upsert_card(
        session,
        "Structure — Hiérarchie thématique",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # `v_repartition_all` (phase B) porte déjà la dimension propre
                    # à chaque période : objectif stratégique -> objectif spécifique
                    # en 2021-2027, `domaine_intervention` en 2014-2020. La carte
                    # n'a donc pas à connaître la période, elle lit `niveau1`/
                    # `niveau2` — c'est la vue qui sait ce qu'ils désignent.
                    #
                    # Le treemap de Metabase v0.63.16 n'a que DEUX niveaux
                    # (`treemap.grouping` + `treemap.sub_grouping`), là où
                    # `utils.treemap.build_hierarchy_treemap` en empile trois
                    # (fonds -> niveau1 -> niveau2). Le fonds reste donc un
                    # filtre, et non un niveau : c'est celui des trois qui a déjà
                    # son propre onglet et son propre paramètre. Le renoncement
                    # est dit à l'écran, pas seulement ici.
                    "query": (
                        "SELECT niveau1, niveau2, SUM(engage) AS montant_ue "
                        "FROM v_repartition_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY niveau1, niveau2 ORDER BY 3 DESC"
                    ),
                    "template-tags": filtres(
                        ("periode", "perimetre", "fonds"), repartition, 0, tag_id_c
                    ),
                },
                "database": db_id,
            },
            "display": "treemap",
            "visualization_settings": {
                "treemap.grouping": "niveau1",
                "treemap.sub_grouping": "niveau2",
                "treemap.value": "montant_ue",
            },
        },
    )

    cards["structure_portefeuille"] = upsert_card(
        session,
        "Structure — Portefeuille par périmètre",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Jumeau de `utils.stats.build_portfolio_scatter` : nombre
                    # d'opérations en x, montant moyen en y, montant total en
                    # taille de bulle — ce qui sépare un périmètre à quelques
                    # grosses opérations d'un périmètre à beaucoup de petites.
                    #
                    # Le montant moyen est recalculé APRÈS agrégation
                    # (SUM/SUM) et jamais moyenné : une moyenne de moyennes par
                    # fonds donnerait un nombre qui n'est la moyenne de rien.
                    # `NULLIF` plutôt qu'un CASE : un périmètre à zéro opération
                    # n'existe pas dans la vue, mais la division resterait une
                    # faute qui n'attend que la première ligne vide.
                    "query": (
                        "SELECT perimetre, SUM(n_operations) AS n_operations, "
                        "SUM(engage) / NULLIF(SUM(n_operations), 0) AS montant_moyen, "
                        "SUM(engage) AS montant_ue "
                        "FROM v_engage_all "
                        "WHERE {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY perimetre ORDER BY 4 DESC"
                    ),
                    "template-tags": filtres(
                        ("periode", "perimetre", "fonds"), engage, 10, tag_id_c
                    ),
                },
                "database": db_id,
            },
            "display": "scatter",
            "visualization_settings": {
                "graph.dimensions": ["perimetre"],
                "graph.metrics": ["montant_moyen"],
                "scatter.bubble": "montant_ue",
                "graph.x_axis.title_text": "Nombre d'opérations",
                "graph.y_axis.title_text": "Montant UE moyen par opération (€)",
            },
        },
    )

    cards["structure_par_habitant"] = upsert_card(
        session,
        "Structure — Montant UE par habitant",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # `public.region_metadata`, qualifié : la cible PostgreSQL de
                    # dbt (#135) expose un `dbt_spike.region_metadata` homonyme,
                    # à trois colonnes seulement — et c'est LUI que Metabase a
                    # synchronisé. Un nom nu se résoudrait au `search_path`, donc
                    # à une table qui n'a pas `population`.
                    #
                    # INNER JOIN volontaire : `national` et `interregional` n'ont
                    # pas de population, et un montant par habitant n'y veut rien
                    # dire. Ils sortent du classement plutôt que d'y figurer à
                    # zéro — 18 périmètres sur 19 en 2014-2020, 19 sur 21 en
                    # 2021-2027.
                    "query": (
                        "SELECT v_engage_all.perimetre, v_engage_all.fonds, "
                        "SUM(v_engage_all.engage) / m.population AS montant_par_habitant, "
                        "SUM(v_engage_all.engage) AS montant_ue, m.population "
                        "FROM v_engage_all "
                        "JOIN public.region_metadata m ON m.region = v_engage_all.perimetre "
                        "WHERE m.population IS NOT NULL "
                        "AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY v_engage_all.perimetre, v_engage_all.fonds, m.population "
                        "ORDER BY 3 DESC"
                    ),
                    "template-tags": filtres(
                        ("periode", "perimetre", "fonds"), engage, 20, tag_id_c
                    ),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["perimetre", "fonds"],
                "graph.metrics": ["montant_par_habitant"],
                "stackable.stack_type": "stacked",
                "series_settings": SERIES_FONDS,
            },
        },
    )

    cards["structure_rup"] = upsert_card(
        session,
        "Structure — Allocation additionnelle ultrapériphérique (RUP)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Pas de filtre de période : l'allocation RUP de l'art. 349
                    # TFUE n'est chargée que pour 2021-2027 (11 lignes, 7
                    # périmètres). Une carte filtrable sur une période qu'elle ne
                    # porte pas se viderait sans rien expliquer.
                    #
                    # `allocations_rup` est CONTENUE dans `programme_totals`, pas
                    # en plus : la colonne « dotation de base » est donc une
                    # SOUSTRACTION, jamais un second poste à additionner. C'est
                    # exactement la présentation de l'expander Streamlit
                    # (1_Vue_Régionale.py), et l'erreur que la table nue invite à
                    # commettre.
                    "query": (
                        "SELECT allocations_rup.perimetre, allocations_rup.fonds, "
                        "t.montant_ue - allocations_rup.montant_ue "
                        "  AS dotation_categorie_de_base, "
                        "allocations_rup.montant_ue AS allocation_rup, "
                        "t.montant_ue AS total_programme "
                        "FROM allocations_rup "
                        "JOIN public.programme_totals t "
                        "  ON t.region = allocations_rup.perimetre "
                        " AND t.fonds = allocations_rup.fonds "
                        " AND t.periode = allocations_rup.periode "
                        "WHERE {{perimetre}} AND {{fonds}} "
                        "ORDER BY allocations_rup.perimetre, allocations_rup.fonds"
                    ),
                    "template-tags": filtres(("perimetre", "fonds"), rup, 30, tag_id_c),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {},
        },
    )

    cards["pilotage_trajectoire_2014_2020"] = upsert_card(
        session,
        "Pilotage — Engagement cumulé 2014-2020 (Synergie seul)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # La trajectoire 2014-2020 que la phase A annonçait, livrée
                    # sur le seul périmètre que la donnée autorise.
                    #
                    # `date_programmation` n'existe que sur Synergie : 100 % des
                    # lignes y sont datées, 0 % sur les cinq autres sources de la
                    # période. Bretagne, Normandie et Nouvelle-Aquitaine ne la
                    # portent pas, et l'arbitrage #95 refuse de lui substituer
                    # `date_debut`, qui date autre chose — la courbe changerait
                    # de sens sans changer de nom. Synergie pèse 59 % du montant
                    # 2014-2020 : le titre et l'encart le disent, plutôt que de
                    # laisser croire à un total de période.
                    #
                    # Aucun risque de double-comptage ici malgré la lecture
                    # directe d'`operations` : le filtre sur une source UNIQUE
                    # est précisément ce que les règles de substitution et
                    # d'addition de #68/#95 arbitrent entre plusieurs.
                    "query": (
                        "SELECT mois, SUM(montant_mois) OVER (ORDER BY mois) AS montant_cumule "
                        "FROM (SELECT date_trunc('month', date_programmation) AS mois, "
                        "SUM(montant_ue) AS montant_mois FROM operations "
                        f"WHERE source_id = '{SOURCE_SYNERGIE_2014_2020}' "
                        "AND date_programmation IS NOT NULL "
                        "AND {{fonds}} GROUP BY 1) t ORDER BY mois"
                    ),
                    "template-tags": filtres(("fonds",), ops, 40, tag_id_c),
                },
                "database": db_id,
            },
            "display": "line",
            "visualization_settings": {},
        },
    )

    # ------------------------------------------------- Phase D : Analyses & contrôle

    # Radical dédié pour que les tag_id de la Phase D ne chevauchent pas ceux des
    # Phases A/B (tag_id, décades 10-98) ni C (tag_id_c, décades 0-40).
    tag_id_d = "b1000000-0000-0000-0000-0000000002%02d"

    # Les cartes d'analyse travaillent sur `operations` (données par opération),
    # pas sur les vues agrégées. Le filtre périmètre porte donc sur
    # `operations.region` et non `v_engage_all.perimetre` : les périmètres
    # 'national' et 'interregional' (region NULL ou flag sans valeur de région)
    # ne matchent pas et la carte est vide — comportement voulu, une analyse de
    # distribution sur 398 opérations du volet national ne serait pas instructive.
    # Le texte d'accompagnement du dashboard le dit.

    cards["analyse_stats_fonds"] = upsert_card(
        session,
        "Analyse — Statistiques descriptives par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, COUNT(*) AS nb_projets, "
                        "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY montant_ue) AS mediane, "
                        "STDDEV(montant_ue) AS ecart_type, "
                        "CASE WHEN PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY montant_ue) > 0 "
                        "THEN STDDEV(montant_ue) / PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY montant_ue) "
                        "ELSE 0 END AS cv "
                        "FROM operations "
                        "WHERE montant_ue IS NOT NULL "
                        "AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY fonds ORDER BY mediane DESC"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 0, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {
                "column_settings": {
                    '["name","mediane"]': {"number_style": "decimal", "decimals": 0},
                    '["name","ecart_type"]': {"number_style": "decimal", "decimals": 0},
                    '["name","cv"]': {"number_style": "decimal", "decimals": 2},
                },
            },
        },
    )

    cards["analyse_histogramme"] = upsert_card(
        session,
        "Analyse — Distribution des montants UE (log)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Histogramme sur des tranches logarithmiques. Metabase n'a pas
                    # de binning log natif : on calcule les tranches en SQL avec
                    # width_bucket sur log10(montant_ue), puis on reconvertit les
                    # bornes en euros pour l'affichage. 50 bins sur [0, 9] = ordres
                    # de grandeur de 1 € à 1 Md€.
                    "query": (
                        "WITH bins AS ("
                        "  SELECT width_bucket(log(montant_ue), 0, 9, 50) AS bin, fonds "
                        "  FROM operations "
                        "  WHERE montant_ue > 0 "
                        "  AND {{periode}} AND {{perimetre}} AND {{fonds}}"
                        ") "
                        "SELECT bin, "
                        "CONCAT(TO_CHAR(POWER(10, (bin - 1) * 9.0 / 50), 'FM999G999G999G999'), "
                        "' - ', "
                        "TO_CHAR(POWER(10, bin * 9.0 / 50), 'FM999G999G999G999'), ' €') "
                        "AS tranche, "
                        "fonds, COUNT(*) AS n_operations "
                        "FROM bins GROUP BY bin, fonds ORDER BY bin, fonds"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 10, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["tranche", "fonds"],
                "graph.metrics": ["n_operations"],
                "stackable.stack_type": "stacked",
                "graph.x_axis.title_text": "Montant UE (€, échelle log)",
                "graph.y_axis.title_text": "Nombre d'opérations",
                "series_settings": SERIES_FONDS,
            },
        },
    )

    cards["analyse_boxplot_stats"] = upsert_card(
        session,
        "Analyse — Quartiles et dispersion par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Metabase n'a pas de boxplot natif. Cette table donne les
                    # cinq nombres clés (min, Q1, médiane, Q3, max) et les bornes
                    # des moustaches IQR — ce que le boxplot Streamlit montre
                    # graphiquement. Le lecteur s'en sert comme référence pour
                    # situer les opérations atypiques de la table voisine.
                    "query": (
                        "SELECT fonds, "
                        "MIN(montant_ue) AS minimum, "
                        "PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY montant_ue) AS q1, "
                        "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY montant_ue) AS mediane, "
                        "PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY montant_ue) AS q3, "
                        "MAX(montant_ue) AS maximum, "
                        "GREATEST(MIN(montant_ue), "
                        "  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY montant_ue) "
                        "  - 1.5 * (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY montant_ue) "
                        "    - PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY montant_ue))) AS borne_basse, "
                        "LEAST(MAX(montant_ue), "
                        "  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY montant_ue) "
                        "  + 1.5 * (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY montant_ue) "
                        "    - PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY montant_ue))) AS borne_haute "
                        "FROM operations "
                        "WHERE montant_ue IS NOT NULL "
                        "AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "GROUP BY fonds ORDER BY mediane DESC"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 20, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {
                "column_settings": {
                    '["name","minimum"]': {"number_style": "decimal", "decimals": 0},
                    '["name","q1"]': {"number_style": "decimal", "decimals": 0},
                    '["name","mediane"]': {"number_style": "decimal", "decimals": 0},
                    '["name","q3"]': {"number_style": "decimal", "decimals": 0},
                    '["name","maximum"]': {"number_style": "decimal", "decimals": 0},
                    '["name","borne_basse"]': {"number_style": "decimal", "decimals": 0},
                    '["name","borne_haute"]': {"number_style": "decimal", "decimals": 0},
                },
            },
        },
    )

    cards["analyse_outliers"] = upsert_card(
        session,
        "Analyse — Opérations à montant atypique (IQR par fonds)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Méthode IQR par fonds, identique à `detect_outliers` côté
                    # Python : Q1 - 1.5*IQR ou Q3 + 1.5*IQR, calculé séparément
                    # par fonds. Sans groupement par fonds, les ordres de grandeur
                    # très différents entre FEDER/FSE+/FTJ produisent des faux
                    # positifs (constaté : 502 opérations FEDER à tort).
                    "query": (
                        "WITH quartiles AS ("
                        "  SELECT fonds, "
                        "    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY montant_ue) AS q1, "
                        "    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY montant_ue) AS q3 "
                        "  FROM operations "
                        "  WHERE montant_ue IS NOT NULL "
                        "  AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "  GROUP BY fonds"
                        ") "
                        "SELECT operations.intitule_projet, operations.nom_beneficiaire, "
                        "operations.fonds, operations.montant_ue "
                        "FROM operations "
                        "JOIN quartiles q ON q.fonds = operations.fonds "
                        "WHERE operations.montant_ue IS NOT NULL "
                        "AND (operations.montant_ue < q.q1 - 1.5 * (q.q3 - q.q1) "
                        "  OR operations.montant_ue > q.q3 + 1.5 * (q.q3 - q.q1)) "
                        "AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "ORDER BY operations.montant_ue DESC "
                        "LIMIT 50"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 30, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {
                "column_settings": {
                    '["name","montant_ue"]': {"number_style": "decimal", "decimals": 0},
                },
            },
        },
    )

    cards["analyse_top_beneficiaires"] = upsert_card(
        session,
        "Analyse — Top 15 bénéficiaires par montant UE",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Jumeau de `build_pareto_beneficiaires` : les 15 plus gros
                    # bénéficiaires par montant cumulé. Le % cumulé est calculé
                    # sur l'ensemble des bénéficiaires, pas seulement les 15
                    # affichés — c'est la lecture Pareto.
                    "query": (
                        "WITH agg AS ("
                        "  SELECT nom_beneficiaire, SUM(montant_ue) AS montant_ue_total "
                        "  FROM operations "
                        "  WHERE montant_ue IS NOT NULL AND nom_beneficiaire IS NOT NULL "
                        "  AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "  GROUP BY nom_beneficiaire"
                        "), "
                        "ranked AS ("
                        "  SELECT *, "
                        "    SUM(montant_ue_total) OVER (ORDER BY montant_ue_total DESC) "
                        "    / SUM(montant_ue_total) OVER () AS cumule_pct, "
                        "    ROW_NUMBER() OVER (ORDER BY montant_ue_total DESC) AS rang "
                        "  FROM agg"
                        ") "
                        "SELECT nom_beneficiaire, montant_ue_total, cumule_pct "
                        "FROM ranked WHERE rang <= 15 ORDER BY rang"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 40, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "graph.dimensions": ["nom_beneficiaire"],
                "graph.metrics": ["montant_ue_total"],
                "graph.x_axis.title_text": "Bénéficiaire",
                "graph.y_axis.title_text": "Montant UE cumulé (€)",
            },
        },
    )

    cards["analyse_lorenz"] = upsert_card(
        session,
        "Analyse — Courbe de Lorenz (concentration par bénéficiaire)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Courbe de Lorenz : % cumulé de bénéficiaires (du plus petit
                    # au plus grand) vs % cumulé du montant UE. Plus la courbe
                    # s'éloigne de la diagonale d'égalité parfaite, plus le montant
                    # est concentré.
                    #
                    # Échantillonnée en 100 centiles plutôt qu'un point par
                    # bénéficiaire : Metabase tronque à 2 000 lignes, et 7 000+
                    # bénéficiaires dépassent cette limite — la courbe s'arrêtait
                    # à ~26 % au lieu de monter à 100 %. Avec NTILE(100), la
                    # courbe a exactement 100 points, suffisants pour la lecture.
                    "query": (
                        "WITH agg AS ("
                        "  SELECT nom_beneficiaire, SUM(montant_ue) AS montant_total "
                        "  FROM operations "
                        "  WHERE montant_ue IS NOT NULL AND nom_beneficiaire IS NOT NULL "
                        "  AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "  GROUP BY nom_beneficiaire"
                        "), "
                        "ranked AS ("
                        "  SELECT montant_total, "
                        "    NTILE(100) OVER (ORDER BY montant_total ASC) AS centile, "
                        "    SUM(montant_total) OVER () AS somme_totale "
                        "  FROM agg"
                        "), "
                        "par_centile AS ("
                        "  SELECT centile, "
                        "    SUM(montant_total) AS montant_centile, "
                        "    MIN(somme_totale) AS somme_totale "
                        "  FROM ranked GROUP BY centile"
                        ") "
                        "SELECT centile::float / 100 AS pct_beneficiaires, "
                        "SUM(montant_centile) OVER (ORDER BY centile) / somme_totale "
                        "AS pct_montant "
                        "FROM par_centile ORDER BY centile"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 50, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "line",
            "visualization_settings": {
                "graph.dimensions": ["pct_beneficiaires"],
                "graph.metrics": ["pct_montant"],
                "graph.x_axis.title_text": "% cumulé des bénéficiaires",
                "graph.y_axis.title_text": "% cumulé du montant UE",
            },
        },
    )

    cards["analyse_coherence"] = upsert_card(
        session,
        "Analyse — Cohérence des montants (UE > dépenses éligibles)",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    # Opérations où le montant UE dépasse le total des dépenses
                    # éligibles — taux de cofinancement > 100 %, normalement
                    # impossible. Contrôle de cohérence, pas de distribution.
                    "query": (
                        "SELECT intitule_projet, nom_beneficiaire, fonds, "
                        "depenses_eligibles, montant_ue, "
                        "CASE WHEN depenses_eligibles > 0 "
                        "THEN montant_ue / depenses_eligibles ELSE NULL END AS taux "
                        "FROM operations "
                        "WHERE montant_ue IS NOT NULL AND depenses_eligibles IS NOT NULL "
                        "AND montant_ue > depenses_eligibles "
                        "AND {{periode}} AND {{perimetre}} AND {{fonds}} "
                        "ORDER BY montant_ue DESC"
                    ),
                    "template-tags": filtres(("periode", "perimetre", "fonds"), ops, 60, tag_id_d, colonnes={"perimetre": "region"}),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {
                "column_settings": {
                    '["name","depenses_eligibles"]': {"number_style": "decimal", "decimals": 0},
                    '["name","montant_ue"]': {"number_style": "decimal", "decimals": 0},
                    '["name","taux"]': {"number_style": "percent", "decimals": 1},
                },
            },
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
                ("heading", "Où va l'argent, par thématique", 0, 0, 24, 1),
                ("card", "structure_treemap", 1, 0, 24, 10),
                ("text",
                 "**Deux niveaux, pas trois.** Le treemap de Metabase n'accepte "
                 "qu'un groupement et un sous-groupement, là où la version "
                 "Streamlit empile fonds → objectif stratégique → objectif "
                 "spécifique. Le **fonds** reste donc un filtre plutôt qu'un "
                 "niveau : c'est celui des trois qui a déjà son onglet et son "
                 "paramètre.\n\n"
                 "**Ce que montre chaque période n'est pas la même chose.** En "
                 "2021-2027, les deux niveaux sont l'objectif stratégique puis "
                 "l'objectif spécifique. En 2014-2020, la source ne porte aucune "
                 "de ces deux dimensions (#82) : le premier niveau est le "
                 "**domaine d'intervention** et il n'y a pas de second — le "
                 "treemap y est plat, ce n'est pas un défaut d'affichage.",
                 11, 0, 24, 4),
                ("text",
                 "⚠️ **Le treemap 2014-2020 est difficilement lisible, et c'est "
                 "un problème de données, pas de visualisation.** Deux causes, "
                 "toutes deux visibles à l'écran plutôt que masquées :\n\n"
                 "- **93 % du montant de la période est en `Non renseigné`** : le "
                 "domaine d'intervention n'est porté que par trois des six "
                 "sources. Filtrer ces opérations rendrait le treemap muet sur "
                 "l'essentiel de la période sans que rien ne l'explique.\n"
                 "- **Les libellés ne sont pas harmonisés** : 138 valeurs "
                 "distinctes, où un même domaine apparaît sous plusieurs "
                 "orthographes (`117.0`, `117 Amélioration…`, `117 - "
                 "Amélioration…`, et une version tronquée). Le treemap en fait "
                 "donc plusieurs pavés là où il n'y a qu'un domaine.\n\n"
                 "L'harmonisation est un chantier de pipeline, pas de "
                 "visualisation : elle est suivie dans son issue dédiée, en "
                 "amont du Parquet.",
                 15, 0, 24, 5),
            ]),
            ("Programmes", [
                ("heading", "Forme du portefeuille", 0, 0, 24, 1),
                ("card", "structure_portefeuille", 1, 0, 24, 8),
                ("text",
                 "Chaque bulle est un périmètre : le **nombre d'opérations** en "
                 "abscisse, le **montant UE moyen par opération** en ordonnée, le "
                 "**montant total** en taille. Deux périmètres au même total s'y "
                 "distinguent — beaucoup de petites opérations en bas à droite, "
                 "quelques grosses en haut à gauche.\n\n"
                 "Le montant moyen est recalculé sur les totaux du périmètre, "
                 "jamais moyenné à partir des moyennes par fonds : une moyenne "
                 "de moyennes ne serait la moyenne de rien.",
                 9, 0, 24, 3),
                ("heading", "Montant UE par habitant", 12, 0, 24, 1),
                ("card", "structure_par_habitant", 13, 0, 24, 9),
                ("text",
                 "**Le volet national et l'interrégional sont absents de ce "
                 "classement, volontairement** : ils n'ont pas de population, et "
                 "un montant par habitant n'y a pas de sens. Les y faire figurer "
                 "à zéro laisserait croire à une sous-dotation.\n\n"
                 "Montant par habitant et taux de consommation ne mesurent pas la "
                 "même chose : l'un rapporte l'enveloppe à la population, l'autre "
                 "l'engagé à ce qui était programmé. Le second est dans l'onglet "
                 "*Comparaison régionale* du dashboard **Pilotage**.",
                 22, 0, 24, 4),
                ("heading", "Allocation additionnelle ultrapériphérique (RUP)", 26, 0, 24, 1),
                ("card", "structure_rup", 27, 0, 24, 6),
                ("text",
                 "Allocation spécifique de l'**art. 349 TFUE** pour les régions "
                 "ultrapériphériques, **2021-2027 uniquement** — quelle que soit "
                 "la Période choisie, cette table ne porte pas 2014-2020.\n\n"
                 "⚠️ **Ces montants ne s'ajoutent pas au programmé** : "
                 "l'allocation RUP est **contenue** dans le total programmé du "
                 "périmètre. C'est pourquoi la dotation de catégorie de base est "
                 "affichée comme une soustraction — additionner les deux "
                 "premières colonnes redonne la troisième, et compter la RUP en "
                 "plus la compterait deux fois.\n\n"
                 "La ligne `national` n'est pas une erreur : la part FSE+ de "
                 "l'allocation est portée par une ligne nationale de l'Accord de "
                 "partenariat, pas ventilée par région.",
                 33, 0, 24, 5),
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
                ("heading", "2021-2027 — engagement cumulé", 0, 0, 24, 1),
                ("card", "pilotage_trajectoire", 1, 0, 24, 8),
                ("heading", "2014-2020 — engagement cumulé (Synergie seul)", 9, 0, 24, 1),
                ("card", "pilotage_trajectoire_2014_2020", 10, 0, 24, 8),
                ("text",
                 "**Les deux courbes ignorent le filtre Période** : chacune est "
                 "scopée à la sienne, et son titre le dit. Le filtre Fonds, lui, "
                 "les pilote toutes les deux.\n\n"
                 "**Elles ne datent pas la même chose, et ce n'est pas rattrapable "
                 "avec les sources actuelles.** La courbe 2021-2027 cumule sur la "
                 "**date de début d'opération**, seule date que porte le fichier "
                 "conventionné. La courbe 2014-2020 cumule sur la **date de "
                 "programmation**, qui est la bonne date pour une trajectoire "
                 "d'engagement. Comparer leurs pentes entre périodes n'a donc pas "
                 "de sens — ce que ce projet ne cherche de toute façon pas à "
                 "faire, les logiques de programmation ayant changé et REACT-EU "
                 "ayant déformé la fin de la période 2014-2020.",
                 18, 0, 24, 5),
                ("text",
                 "⚠️ **La courbe 2014-2020 ne couvre que Synergie, soit 59 % du "
                 "montant de la période.** `date_programmation` y est renseignée "
                 "à 100 %, et à 0 % sur les cinq autres sources : les fichiers "
                 "régionaux de Bretagne, Normandie et Nouvelle-Aquitaine et le "
                 "fichier PON FSE ne la portent pas.\n\n"
                 "Leur `date_debut` est, elle, renseignée partout — mais lui "
                 "substituer la date de début reviendrait à dater autre chose que "
                 "la programmation sous le même nom (arbitrage #95). Le périmètre "
                 "partiel est donc annoncé plutôt que comblé par une date "
                 "approchante. L'étude de cette substitution, et de la manière de "
                 "la signaler à l'écran si elle était retenue, fait l'objet de son "
                 "issue dédiée.",
                 23, 0, 24, 5),
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
                ("heading", "Statistiques descriptives par fonds", 0, 0, 24, 1),
                ("card", "analyse_stats_fonds", 1, 0, 24, 5),
                ("text",
                 "La **médiane** et l'**écart-type** mesurent la dispersion des "
                 "montants au sein d'un fonds. Le **coefficient de variation** "
                 "(écart-type / médiane) rend cette dispersion comparable entre "
                 "fonds d'ordres de grandeur très différents (ex. FTJ vs FSE+).",
                 6, 0, 24, 2),
                ("heading", "Distribution des montants UE", 8, 0, 24, 1),
                ("card", "analyse_histogramme", 9, 0, 24, 8),
                ("text",
                 "Histogramme en **échelle logarithmique** : les montants s'étalent "
                 "sur plusieurs ordres de grandeur (de quelques milliers à plusieurs "
                 "millions d'euros), ce qui rend une échelle linéaire illisible. "
                 "Chaque barre empile les fonds sur une tranche de montant.",
                 17, 0, 24, 2),
                ("heading", "Quartiles et moustaches IQR par fonds", 19, 0, 24, 1),
                ("card", "analyse_boxplot_stats", 20, 0, 24, 5),
                ("text",
                 "Metabase n'a pas de boîte à moustaches (boxplot) native : ce "
                 "tableau porte les mêmes cinq nombres clés (minimum, Q1, médiane, "
                 "Q3, maximum) et les bornes des moustaches IQR. Les opérations "
                 "hors de l'intervalle [borne basse, borne haute] sont listées dans "
                 "la table *Opérations atypiques* ci-dessous.",
                 25, 0, 24, 3),
                ("heading", "Opérations à montant atypique", 28, 0, 24, 1),
                ("card", "analyse_outliers", 29, 0, 24, 8),
                ("text",
                 "Opérations dont le montant sort de [Q1 − 1,5×IQR, Q3 + 1,5×IQR], "
                 "**calculé séparément par fonds** — sans quoi les ordres de grandeur "
                 "très différents entre FEDER et FSE+ produisent des faux positifs "
                 "(constaté sur 2021-2027 : 502 opérations FEDER signalées à tort par "
                 "une borne unique). Un montant atypique est un point à examiner, pas "
                 "une anomalie : un projet structurant légitime peut être un outlier.",
                 37, 0, 24, 3),
            ]),
            ("Concentration", [
                ("heading", "Top 15 bénéficiaires par montant UE", 0, 0, 24, 1),
                ("card", "analyse_top_beneficiaires", 1, 0, 24, 8),
                ("text",
                 "Bénéficiaires cumulant le plus de montant UE, tous projets confondus "
                 "dans le périmètre affiché — vue d'ensemble des acteurs les plus "
                 "représentés dans le portefeuille.",
                 9, 0, 24, 2),
                ("heading", "Courbe de Lorenz", 11, 0, 24, 1),
                ("card", "analyse_lorenz", 12, 0, 24, 8),
                ("text",
                 "% cumulé de bénéficiaires (du plus petit au plus grand montant) "
                 "vs % cumulé du montant UE : plus la courbe s'éloigne de la "
                 "diagonale d'égalité parfaite, plus le montant est concentré sur "
                 "peu de bénéficiaires. En complément du classement ci-dessus, "
                 "cette courbe montre la **forme** de la concentration, pas "
                 "seulement le podium.",
                 20, 0, 24, 3),
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
                ("heading", "Cohérence des montants", 0, 0, 24, 1),
                ("card", "analyse_coherence", 1, 0, 24, 8),
                ("text",
                 "Opérations dont le **montant UE dépasse le total des dépenses "
                 "éligibles** — taux de cofinancement supérieur à 100 %, normalement "
                 "impossible quel que soit le fonds (y compris REACT-EU, plafonné à "
                 "100 % par le règlement 2020/2221 art. 92 ter §12). Un écart ici est "
                 "un signal de cohérence de la source, pas une question de distribution "
                 "statistique.\n\n"
                 "Si le tableau est vide, c'est bon signe : aucune incohérence sur "
                 "le périmètre affiché.",
                 9, 0, 24, 3),
                ("text",
                 "**Filtre Périmètre sur les cartes d'analyse par opération.** "
                 "Le filtre porte sur `operations.region` : les périmètres "
                 "« national » et « interrégional » (opérations sans région dans la "
                 "table source) produisent un résultat vide — l'analyse de "
                 "distribution n'y serait pas instructive.",
                 12, 0, 24, 2),
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
