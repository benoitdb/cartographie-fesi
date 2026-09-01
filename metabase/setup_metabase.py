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

    print(f"Dashboard prêt : {MB_URL}/dashboard/{dash_id}")


if __name__ == "__main__":
    main()
