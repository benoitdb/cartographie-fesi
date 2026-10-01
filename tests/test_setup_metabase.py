"""Contrats du provisionnement Metabase qui ne demandent pas la stack Docker."""

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "metabase"))

pytest.importorskip("requests", reason="requests est requis par le provisionnement Metabase")

import setup_metabase as setup  # noqa: E402


class Reponse:
    def __init__(self, contenu=None):
        self.contenu = contenu

    def json(self):
        return self.contenu

    def raise_for_status(self):
        return None


class SessionGeoJSON:
    def __init__(self):
        self.ecritures = []

    def get(self, url):
        assert url == f"{setup.MB_URL}/api/setting/custom-geojson"
        return Reponse({})

    def put(self, url, json):
        self.ecritures.append((url, json))
        return Reponse()


def test_les_url_geojson_sont_epinglees_sur_une_revision_git():
    """`main` ferait varier silencieusement les contours entre deux installations."""
    assert re.fullmatch(r"[0-9a-f]{40}", setup.GEOJSON_REVISION)

    for url in (setup.GEOJSON_METROPOLE_URL, setup.GEOJSON_DROMCOM_URL):
        assert f"/{setup.GEOJSON_REVISION}/" in url
        assert "/main/" not in url


def test_le_provisionnement_enregistre_les_deux_contours_epingles():
    session = SessionGeoJSON()

    setup.ensure_geojson_map(session)

    assert session.ecritures == [
        (
            f"{setup.MB_URL}/api/setting/custom-geojson",
            {
                "value": {
                    "fesi_metropole": {
                        "name": "Régions métropole (FESI)",
                        "url": setup.GEOJSON_METROPOLE_URL,
                        "region_key": "nom",
                        "region_name": "nom",
                        "builtin": False,
                    },
                    "fesi_dromcom": {
                        "name": "Régions DROM-COM (FESI)",
                        "url": setup.GEOJSON_DROMCOM_URL,
                        "region_key": "nom",
                        "region_name": "nom",
                        "builtin": False,
                    },
                }
            },
        )
    ]
