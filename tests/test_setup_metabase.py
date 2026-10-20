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


class SessionMetadonnees:
    def __init__(self, tables):
        self.tables = tables

    def get(self, url):
        assert url == f"{setup.MB_URL}/api/database/7/metadata"
        return Reponse({"tables": self.tables})


def test_deux_tables_homonymes_de_schemas_differents_ne_se_masquent_pas():
    # Le seed dbt `region_metadata` (3 colonnes) a longtemps été synchronisé à
    # côté de `public.region_metadata` : repérées par leur seul nom, l'une
    # écrasait l'autre selon l'ordre renvoyé par Metabase (#231).
    session = SessionMetadonnees([
        {"schema": "public", "name": "region_metadata", "fields": [{"name": "population", "id": 1}]},
        {"schema": "reference", "name": "region_metadata", "fields": [{"name": "region", "id": 2}]},
        {"schema": "marts", "name": "engage_all", "fields": [{"name": "perimetre", "id": 3}]},
    ])

    tables = setup.table_fields(session, 7)

    assert tables["public.region_metadata"] == {"population": 1}
    assert tables["reference.region_metadata"] == {"region": 2}
    assert tables["marts.engage_all"] == {"perimetre": 3}


def test_les_cartes_lisent_les_marts_et_plus_aucune_vue_v():
    # ADR 002 : Metabase lit les marts dbt. Une carte restée sur une vue `v_*`
    # continuerait de marcher jusqu'au retrait des vues (PR 2 de #231), puis
    # casserait sans bruit.
    source = (RACINE / "metabase" / "setup_metabase.py").read_text(encoding="utf-8")
    # Toute chaîne qui porte un mot-clé SQL : un fragment de requête ne commence
    # pas forcément par SELECT (« SUM(…) AS n FROM … »).
    requetes = [c for c in re.findall(r'"[^"\n]*"', source) if re.search(r"\b(SELECT|FROM|JOIN)\b", c)]
    assert requetes, "aucune requête trouvée : le motif ne voit plus le SQL des cartes"
    assert not [r for r in requetes if re.search(r"\bv_[a-z0-9_]+", r)]
    assert all(t.startswith(("marts.", "public.")) for t in setup.VUES_UNIFIEES)


def test_une_table_listee_sans_ses_colonnes_n_est_pas_encore_synchronisee():
    # Metabase liste une table nouvellement découverte avant d'en lire les
    # champs : la bascule sur les marts (#231) a buté sur `marts.engage_all`
    # présente, mais sans `periode`.
    assert not setup._synchronisees({"marts.engage_all": {}}, ("marts.engage_all",))
    assert not setup._synchronisees({}, ("marts.engage_all",))
    assert setup._synchronisees({"marts.engage_all": {"periode": 1}}, ("marts.engage_all",))
