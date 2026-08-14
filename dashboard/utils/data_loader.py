import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = REPO_ROOT / "data" / "processed" / "data.json"
GEOJSON_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "regions-metropole.geojson"
REGION_METADATA_PATH = REPO_ROOT / "data" / "processed" / "region_metadata.json"


@st.cache_data
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_geojson():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_region_metadata():
    with open(REGION_METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)
