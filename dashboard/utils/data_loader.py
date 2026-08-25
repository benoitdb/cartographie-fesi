import json
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PATH = REPO_ROOT / "data" / "processed" / "data.json"
DATA_2014_2020_PATH = REPO_ROOT / "data" / "processed" / "data_2014-2020.json"
GEOJSON_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "regions-metropole.geojson"
GEOJSON_DROMCOM_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "regions-dromcom.geojson"
DROMCOM_CODES_POSTAUX_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "dromcom_codes_postaux.json"
REGION_METADATA_PATH = REPO_ROOT / "data" / "processed" / "region_metadata.json"
PROGRAMME_TOTALS_PATH = REPO_ROOT / "data" / "processed" / "programme_totals.json"
PROGRAMME_DETAIL_PATH = REPO_ROOT / "data" / "processed" / "programme_detail.json"
BENEFICIAIRES_FUZZY_PATH = REPO_ROOT / "data" / "processed" / "beneficiaires_fuzzy.json"
DOTATIONS_OS_PATH = REPO_ROOT / "data" / "processed" / "dotations_os.json"
INTERREG_PATH = REPO_ROOT / "data" / "processed" / "interreg.json"
TRANSFERTS_SOLIDARITE_PATH = REPO_ROOT / "data" / "processed" / "transferts_solidarite.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


@st.cache_data
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_data_2014_2020():
    """Jeu 2014-2020 (extraction Synergie), **fichier distinct** de `data.json`.

    Un fichier par période, et un chargeur par fichier : les deux pèsent 45 et
    42 Mo, un chargeur unique qui les lirait tous les deux mettrait ~100 Mo en
    mémoire pour n'en afficher qu'un (arbitrage 1 de l'issue #12). Seule la page
    qui appelle cette fonction paie le chargement, et `st.cache_data` fait qu'une
    session ne le paie qu'une fois.

    Les libellés de colonnes des opérations ne sont **pas** ceux de `data.json` :
    passer le résultat par `utils.periodes.normaliser_operations` avant de le
    donner au reste du dashboard (issue #83)."""
    with open(DATA_2014_2020_PATH, encoding="utf-8") as f:
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
def load_dromcom_codes_postaux():
    """Centroïde commune(s) par code postal pour les 6 territoires DROM-COM — voir
    frontend/public/geo/SOURCES.md pour la provenance (dataset La Poste/data.gouv.fr, sauf
    Saint-Martin sourcé séparément depuis Wikidata)."""
    with open(DROMCOM_CODES_POSTAUX_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_region_metadata():
    with open(REGION_METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_programme_totals():
    with open(PROGRAMME_TOTALS_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_programme_detail():
    """Détail non couvert par load_programme_totals() : split FTJ Article 3/4 et enveloppes
    d'assistance technique par fonds, par région (clé "national" pour les programmes
    nationaux) — voir issues #20/#21. {"ftj_article": {région: {"Article 3": montant, ...}},
    "assistance_technique": {région: {fonds: montant}}}."""
    with open(PROGRAMME_DETAIL_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_beneficiaires_fuzzy():
    """Rapprochements approchés de noms de bénéficiaires entre régions disjointes (issue
    #23) : {nom_de_bénéficiaire: cluster_id}, précalculé par
    data-pipeline/beneficiaires_fuzzy.py — voir beneficiaire_matching.py pour la méthode."""
    with open(BENEFICIAIRES_FUZZY_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_dotations_os():
    """Dotations programmées par objectif stratégique, au niveau national uniquement (Tableau
    8 de l'Accord de partenariat, voir data-pipeline/reference/dotations_os.py et issue #21).
    {objectif_stratégique: {fonds: montant}}."""
    with open(DOTATIONS_OS_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_interreg():
    """Liste des 18 programmes Interreg auxquels la France participe (Tableau 10, aucune
    donnée financière ni opération — voir data-pipeline/reference/interreg.py et issue #19).
    [{"cci": str, "intitule": str, "type": "VI-A"|"VI-B"|"VI-D"}]."""
    with open(INTERREG_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_transferts_solidarite():
    """Transferts de solidarité entre catégories de régions vers "Moins développées" (Tableau
    3A/3B de l'Accord de partenariat, voir data-pipeline/reference/transferts_solidarite.py et
    issue #30). Mécanisme national global, non croisable avec data.json — purement
    informationnel. {"transferts": [{"categorie_origine": str, "montants_par_annee":
    {année: montant}, "total_publie": montant, "part_dotation_transferee": float}]}."""
    with open(TRANSFERTS_SOLIDARITE_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_profils_source():
    """Profils de source par période (data-pipeline/profil_source.py), pour la page
    « Validation de la source » (issue #69). Découverts par glob : ajouter une
    période, c'est déposer son `profil_<periode>.json`, sans toucher au dashboard.

    Une entrée par **source** (un fichier) — une même période peut en avoir
    plusieurs (issue #68). Triée par période décroissante puis par libellé de
    source. Chaque entrée : {"source_id", "source_label", "periode",
    "fichier_source", "date_source", "date_generation", "profil": {...}}. Liste
    vide si aucun profil n'est présent."""
    profils = []
    for chemin in PROCESSED_DIR.glob("profil_*.json"):
        with open(chemin, encoding="utf-8") as f:
            profils.append(json.load(f))
    return sorted(
        profils,
        key=lambda p: (p.get("periode", ""), p.get("source_label", "")),
        reverse=True,
    )
