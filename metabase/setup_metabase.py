"""Provisionne l'instance Metabase (issue #121, Phase 1) : connexion PostgreSQL,
carte GeoJSON métropole, dashboard national 2021-2027.

Idempotent et commité, dans le même esprit que `load_data.py`/`verify_aggregates.py` :
le test exploratoire de Phase 0 avait créé ce même dashboard via un script jetable,
jamais versionné — celui-ci le remplace pour de bon.

Portée volontairement limitée à 2021-2027 (`source_id = '2021-2027-conventionnees'`) :
les vues Phase 0 sont scopées par (source_id, periode) et ne blendent jamais
plusieurs sources pour une période (Bretagne/Normandie/Nouvelle-Aquitaine/PON FSE
se chevauchent avec Synergie en 2014-2020, cf. `init/02_views.sql`) — cette fusion
nationale reste un sujet de Phase 2/3, pas construit en SQL. Un dashboard 2014-2020
est un sujet de Phase 3 (cf. issue #121), pas de celui-ci.

Relançable sans effet de bord : chaque étape vérifie si la ressource existe déjà
(par nom) avant de la créer.
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


def fonds_tag(tag_id):
    return {
        "fonds": {
            "id": tag_id,
            "name": "fonds",
            "display-name": "Fonds",
            "type": "text",
            "required": False,
        }
    }


def region_tag(tag_id, tag_name="region", display_name="Région", default=None):
    return {
        tag_name: {
            "id": tag_id,
            "name": tag_name,
            "display-name": display_name,
            "type": "text",
            "required": True,
            "default": default,
        }
    }


def build_cards(session, db_id):
    cards = {}

    cards["n_operations"] = upsert_card(
        session,
        "Nombre d'opérations",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT SUM(n_operations) AS n_operations FROM v_by_fonds "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "[[AND fonds = {{fonds}}]]"
                    ),
                    "template-tags": fonds_tag("a1000000-0000-0000-0000-000000000001"),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["montant_ue_total"] = upsert_card(
        session,
        "Montant UE total",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT SUM(montant_ue_total) AS montant_ue_total FROM v_by_fonds "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "[[AND fonds = {{fonds}}]]"
                    ),
                    "template-tags": fonds_tag("a1000000-0000-0000-0000-000000000002"),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    series_settings = {
        fonds: {"color": color}
        for fonds, color in FONDS_COLORS.items()
        if fonds in FONDS_2021_2027
    }
    cards["par_fonds"] = upsert_card(
        session,
        "Montant UE par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, montant_ue_total FROM v_by_fonds "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "[[AND fonds = {{fonds}}]] ORDER BY fonds"
                    ),
                    "template-tags": fonds_tag("a1000000-0000-0000-0000-000000000003"),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"series_settings": series_settings},
        },
    )

    cards["engagement_cumule"] = upsert_card(
        session,
        "Engagement cumulé",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT mois, SUM(montant_mois) OVER (ORDER BY mois) AS montant_cumule "
                        "FROM (SELECT date_trunc('month', date_convention) AS mois, "
                        "SUM(montant_ue) AS montant_mois FROM operations "
                        f"WHERE source_id = '{SOURCE_2021_2027}' AND date_convention IS NOT NULL "
                        "[[AND fonds = {{fonds}}]] GROUP BY 1) t ORDER BY mois"
                    ),
                    "template-tags": fonds_tag("a1000000-0000-0000-0000-000000000004"),
                },
                "database": db_id,
            },
            "display": "line",
            "visualization_settings": {},
        },
    )

    cards["par_region"] = upsert_card(
        session,
        "Montant UE par région",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT region, montant_ue_total FROM v_by_region "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "[[AND fonds = {{fonds}}]] ORDER BY region"
                    ),
                    "template-tags": fonds_tag("a1000000-0000-0000-0000-000000000005"),
                },
                "database": db_id,
            },
            "display": "map",
            "visualization_settings": {
                "map.type": "region",
                "map.region": "fesi_metropole",
                "map.metric_column": "montant_ue_total",
                "map.dimension_column": "region",
            },
        },
    )

    return cards


DEFAULT_REGION = "Île-de-France"
DEFAULT_REGION_A = "Bretagne"
DEFAULT_REGION_B = "Occitanie"


def build_regional_cards(session, db_id):
    """Phase 2 (issue #121) : équivalent Metabase de `pages/1_Vue_Régionale.py` —
    KPI + pilotage (programmé vs engagé, taux, reste à engager) pour UNE région,
    choisie via le template-tag `region` (texte, pas field-filter — même choix
    que `fonds` en Phase 1, cf. gotchas README). `v_pilotage` (03_pilotage.sql)
    porte déjà les règles de `dashboard/utils/pilotage.py` (reste à engager par
    fonds, planché à 0, jamais programme_total - engage_total)."""
    cards = {}
    tag_id = "a3000000-0000-0000-0000-00000000000%d"

    cards["region_montant_total"] = upsert_card(
        session,
        "Région — Montant UE total",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        f"SELECT montant_ue_total FROM v_by_region "
                        f"WHERE source_id = '{SOURCE_2021_2027}' AND region = {{{{region}}}}"
                    ),
                    "template-tags": region_tag(tag_id % 1, default=DEFAULT_REGION),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["region_n_operations"] = upsert_card(
        session,
        "Région — Nombre d'opérations",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        f"SELECT n_operations FROM v_by_region "
                        f"WHERE source_id = '{SOURCE_2021_2027}' AND region = {{{{region}}}}"
                    ),
                    "template-tags": region_tag(tag_id % 2, default=DEFAULT_REGION),
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    series_settings = {f: {"color": c} for f, c in FONDS_COLORS.items() if f in FONDS_2021_2027}
    cards["region_par_fonds"] = upsert_card(
        session,
        "Région — Montant UE par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        f"SELECT fonds, montant_ue_total FROM v_by_region_fonds "
                        f"WHERE source_id = '{SOURCE_2021_2027}' AND region = {{{{region}}}} ORDER BY fonds"
                    ),
                    "template-tags": region_tag(tag_id % 3, default=DEFAULT_REGION),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"series_settings": series_settings},
        },
    )

    cards["region_pilotage"] = upsert_card(
        session,
        "Région — Programmé vs engagé par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, programme, engage, taux, reste_a_engager FROM v_pilotage "
                        "WHERE periode = '2021-2027' AND perimetre = {{region}} ORDER BY fonds"
                    ),
                    "template-tags": region_tag(tag_id % 4, default=DEFAULT_REGION),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"graph.metrics": ["programme", "engage"], "graph.dimensions": ["fonds"]},
        },
    )

    return cards


def _region_dashcards(cards_layout, param_id, tag_name="region"):
    return [
        {
            "id": -(i + 1),
            "card_id": card["id"],
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y,
            "parameter_mappings": [
                {
                    "parameter_id": param_id,
                    "card_id": card["id"],
                    "target": ["variable", ["template-tag", tag_name]],
                }
            ],
        }
        for i, (card, row, col, size_x, size_y) in enumerate(cards_layout)
    ]


REGIONAL_DASHBOARD_NAME = "FESI — Vue régionale 2021-2027"
REGIONAL_PARAM_ID = "fesi-region-filter"


def ensure_regional_dashboard(session, cards):
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == REGIONAL_DASHBOARD_NAME), None)
    dash_id = existing["id"] if existing else session.post(
        f"{MB_URL}/api/dashboard", json={"name": REGIONAL_DASHBOARD_NAME}
    ).json()["id"]

    layout = [
        (cards["region_montant_total"], 0, 0, 4, 3),
        (cards["region_n_operations"], 4, 0, 4, 3),
        (cards["region_par_fonds"], 0, 3, 8, 5),
        (cards["region_pilotage"], 8, 0, 8, 8),
    ]
    r = session.put(
        f"{MB_URL}/api/dashboard/{dash_id}",
        json={
            "parameters": [
                {
                    "id": REGIONAL_PARAM_ID,
                    "name": "Région",
                    "slug": "region",
                    "type": "string/=",
                    "default": [DEFAULT_REGION],
                }
            ],
            "dashcards": _region_dashcards(layout, REGIONAL_PARAM_ID),
        },
    )
    r.raise_for_status()
    return dash_id


def build_comparateur_cards(session, db_id):
    """Phase 2 : équivalent Metabase de `pages/3_Comparateur.py` — deux régions
    choisies via deux template-tags indépendants (`region_a`, `region_b`), sur
    des cartes communes qui affichent les deux côte à côte (une dimension
    `region` en série), pas deux jeux de cartes dupliqués."""
    cards = {}
    tag_id = "a4000000-0000-0000-0000-00000000000%d"

    def two_regions_tag(id1, id2):
        return {
            **region_tag(id1, "region_a", "Région A", default=DEFAULT_REGION_A),
            **region_tag(id2, "region_b", "Région B", default=DEFAULT_REGION_B),
        }

    cards["comparateur_par_fonds"] = upsert_card(
        session,
        "Comparateur — Montant UE par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT region, fonds, montant_ue_total FROM v_by_region_fonds "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "AND (region = {{region_a}} OR region = {{region_b}}) ORDER BY region, fonds"
                    ),
                    "template-tags": two_regions_tag(tag_id % 1, tag_id % 2),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"graph.dimensions": ["fonds", "region"], "graph.metrics": ["montant_ue_total"]},
        },
    )

    cards["comparateur_taux"] = upsert_card(
        session,
        "Comparateur — Taux de consommation par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT perimetre AS region, fonds, taux FROM v_pilotage "
                        "WHERE periode = '2021-2027' AND (perimetre = {{region_a}} OR perimetre = {{region_b}}) "
                        "ORDER BY region, fonds"
                    ),
                    "template-tags": two_regions_tag(tag_id % 3, tag_id % 4),
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"graph.dimensions": ["fonds", "region"], "graph.metrics": ["taux"]},
        },
    )

    cards["comparateur_kpi"] = upsert_card(
        session,
        "Comparateur — KPI par région",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT region, n_operations, montant_ue_total, montant_ue_moyen FROM v_by_region "
                        f"WHERE source_id = '{SOURCE_2021_2027}' "
                        "AND (region = {{region_a}} OR region = {{region_b}}) ORDER BY region"
                    ),
                    "template-tags": two_regions_tag(tag_id % 5, tag_id % 6),
                },
                "database": db_id,
            },
            "display": "table",
            "visualization_settings": {},
        },
    )

    return cards


COMPARATEUR_DASHBOARD_NAME = "FESI — Comparateur régions 2021-2027"
COMPARATEUR_PARAM_A_ID = "fesi-region-a-filter"
COMPARATEUR_PARAM_B_ID = "fesi-region-b-filter"


def ensure_comparateur_dashboard(session, cards):
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == COMPARATEUR_DASHBOARD_NAME), None)
    dash_id = existing["id"] if existing else session.post(
        f"{MB_URL}/api/dashboard", json={"name": COMPARATEUR_DASHBOARD_NAME}
    ).json()["id"]

    layout = [
        (cards["comparateur_kpi"], 0, 0, 16, 3),
        (cards["comparateur_par_fonds"], 0, 3, 8, 6),
        (cards["comparateur_taux"], 8, 3, 8, 6),
    ]
    dashcards = [
        {
            "id": -(i + 1),
            "card_id": card["id"],
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y,
            "parameter_mappings": [
                {
                    "parameter_id": COMPARATEUR_PARAM_A_ID,
                    "card_id": card["id"],
                    "target": ["variable", ["template-tag", "region_a"]],
                },
                {
                    "parameter_id": COMPARATEUR_PARAM_B_ID,
                    "card_id": card["id"],
                    "target": ["variable", ["template-tag", "region_b"]],
                },
            ],
        }
        for i, (card, row, col, size_x, size_y) in enumerate(layout)
    ]
    r = session.put(
        f"{MB_URL}/api/dashboard/{dash_id}",
        json={
            "parameters": [
                {
                    "id": COMPARATEUR_PARAM_A_ID,
                    "name": "Région A",
                    "slug": "region_a",
                    "type": "string/=",
                    "default": [DEFAULT_REGION_A],
                },
                {
                    "id": COMPARATEUR_PARAM_B_ID,
                    "name": "Région B",
                    "slug": "region_b",
                    "type": "string/=",
                    "default": [DEFAULT_REGION_B],
                },
            ],
            "dashcards": dashcards,
        },
    )
    r.raise_for_status()
    return dash_id


def build_national_cards(session, db_id):
    """Phase 2 : équivalent Metabase de `pages/2_Volet_National.py` — pas de
    template-tag région ici, le périmètre national (`perimetre = 'national'`,
    même clé que `programme_totals`) est fixe. Pas de FEDER national (cf.
    `v_pilotage`, aucune ligne FEDER pour ce périmètre — les opérations
    nationales sont des programmes FSE+/FTJ, ex. France Travail)."""
    cards = {}

    cards["national_montant_total"] = upsert_card(
        session,
        "Volet national — Montant UE total",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        f"SELECT montant_ue_total FROM v_national WHERE source_id = '{SOURCE_2021_2027}'"
                    ),
                    "template-tags": {},
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["national_n_operations"] = upsert_card(
        session,
        "Volet national — Nombre d'opérations",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": f"SELECT n_operations FROM v_national WHERE source_id = '{SOURCE_2021_2027}'",
                    "template-tags": {},
                },
                "database": db_id,
            },
            "display": "scalar",
            "visualization_settings": {},
        },
    )

    cards["national_par_fonds"] = upsert_card(
        session,
        "Volet national — Montant UE par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, engage AS montant_ue_total FROM v_engage_by_perimetre_fonds "
                        "WHERE periode = '2021-2027' AND perimetre = 'national' ORDER BY fonds"
                    ),
                    "template-tags": {},
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {
                "series_settings": {f: {"color": c} for f, c in FONDS_COLORS.items() if f in FONDS_2021_2027}
            },
        },
    )

    cards["national_pilotage"] = upsert_card(
        session,
        "Volet national — Programmé vs engagé par fonds",
        {
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": (
                        "SELECT fonds, programme, engage, taux, reste_a_engager FROM v_pilotage "
                        "WHERE periode = '2021-2027' AND perimetre = 'national' ORDER BY fonds"
                    ),
                    "template-tags": {},
                },
                "database": db_id,
            },
            "display": "bar",
            "visualization_settings": {"graph.metrics": ["programme", "engage"], "graph.dimensions": ["fonds"]},
        },
    )

    return cards


NATIONAL_DASHBOARD_NAME = "FESI — Volet national 2021-2027"


def ensure_national_dashboard(session, cards):
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == NATIONAL_DASHBOARD_NAME), None)
    dash_id = existing["id"] if existing else session.post(
        f"{MB_URL}/api/dashboard", json={"name": NATIONAL_DASHBOARD_NAME}
    ).json()["id"]

    layout = [
        (cards["national_montant_total"], 0, 0, 4, 3),
        (cards["national_n_operations"], 4, 0, 4, 3),
        (cards["national_par_fonds"], 0, 3, 8, 5),
        (cards["national_pilotage"], 8, 0, 8, 8),
    ]
    dashcards = [
        {"id": -(i + 1), "card_id": card["id"], "row": row, "col": col, "size_x": size_x, "size_y": size_y}
        for i, (card, row, col, size_x, size_y) in enumerate(layout)
    ]
    r = session.put(f"{MB_URL}/api/dashboard/{dash_id}", json={"dashcards": dashcards})
    r.raise_for_status()
    return dash_id


DASHBOARD_NAME = "FESI — Vue nationale 2021-2027"
DASHBOARD_PARAM_ID = "fesi-fonds-filter"


def ensure_dashboard(session, cards):
    dashboards = session.get(f"{MB_URL}/api/dashboard").json()
    existing = next((d for d in dashboards if d["name"] == DASHBOARD_NAME), None)
    if existing:
        dash_id = existing["id"]
    else:
        r = session.post(f"{MB_URL}/api/dashboard", json={"name": DASHBOARD_NAME})
        r.raise_for_status()
        dash_id = r.json()["id"]

    layout = [
        ("n_operations", 0, 0, 4, 3),
        ("montant_ue_total", 4, 0, 4, 3),
        ("par_fonds", 0, 3, 8, 5),
        ("engagement_cumule", 8, 0, 8, 5),
        ("par_region", 0, 8, 16, 8),
    ]
    dashcards = [
        {
            "id": -(i + 1),
            "card_id": cards[key]["id"],
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y,
            "parameter_mappings": [
                {
                    "parameter_id": DASHBOARD_PARAM_ID,
                    "card_id": cards[key]["id"],
                    "target": ["variable", ["template-tag", "fonds"]],
                }
            ],
        }
        for i, (key, row, col, size_x, size_y) in enumerate(layout)
    ]

    r = session.put(
        f"{MB_URL}/api/dashboard/{dash_id}",
        json={
            "parameters": [
                {
                    "id": DASHBOARD_PARAM_ID,
                    "name": "Fonds",
                    "slug": "fonds",
                    "type": "string/=",
                    "default": None,
                }
            ],
            "dashcards": dashcards,
        },
    )
    r.raise_for_status()
    return dash_id


def main():
    wait_for_health()
    token = get_session()
    session = requests.Session()
    session.headers["X-Metabase-Session"] = token

    db_id = ensure_database(session)
    ensure_geojson_map(session)
    cards = build_cards(session, db_id)
    dash_id = ensure_dashboard(session, cards)
    print(f"Dashboard national prêt : {MB_URL}/dashboard/{dash_id}")

    regional_cards = build_regional_cards(session, db_id)
    regional_dash_id = ensure_regional_dashboard(session, regional_cards)
    print(f"Dashboard régional prêt : {MB_URL}/dashboard/{regional_dash_id}")

    comparateur_cards = build_comparateur_cards(session, db_id)
    comparateur_dash_id = ensure_comparateur_dashboard(session, comparateur_cards)
    print(f"Dashboard comparateur prêt : {MB_URL}/dashboard/{comparateur_dash_id}")

    national_cards = build_national_cards(session, db_id)
    national_dash_id = ensure_national_dashboard(session, national_cards)
    print(f"Dashboard volet national prêt : {MB_URL}/dashboard/{national_dash_id}")


if __name__ == "__main__":
    main()
