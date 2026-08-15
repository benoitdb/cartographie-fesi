import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = REPO_ROOT / "data" / "processed" / "data.json"
GEOJSON_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "regions-metropole.geojson"
GEOJSON_DROMCOM_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "regions-dromcom.geojson"
REGION_METADATA_PATH = REPO_ROOT / "data" / "processed" / "region_metadata.json"
PROGRAMME_TOTALS_PATH = REPO_ROOT / "data" / "processed" / "programme_totals.json"


@st.cache_data
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_geojson():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_dromcom_geojson():
    """Contours des DROM-COM (Guadeloupe, Martinique, Guyane, La Réunion, Mayotte,
    Saint-Martin) — voir frontend/public/geo/SOURCES.md pour la provenance de chaque contour
    (Saint-Martin vient d'une source différente, absente des découpages IGN/INSEE)."""
    with open(GEOJSON_DROMCOM_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_region_metadata():
    with open(REGION_METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_programme_totals():
    with open(PROGRAMME_TOTALS_PATH, encoding="utf-8") as f:
        return json.load(f)
