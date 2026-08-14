"""Rattachement des opérations à un département, à partir de champs dont le format
est hétérogène (cf. commentaires dans parse_departement_field) — le pipeline de données
n'est pas modifié, cette normalisation est propre à l'affichage du dashboard."""

from pathlib import Path
import json

import plotly.express as px

from utils.plot_style import disable_map_interaction, style_hover, style_map_background

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPARTEMENTS_GEOJSON_PATH = REPO_ROOT / "frontend" / "public" / "geo" / "departements.geojson"

# Alias pour variantes/coquilles observées dans le champ "Département de l'opération"
NAME_ALIASES = {
    "Haute Loire": "Haute-Loire",
    "Pyrénées-Orientiales": "Pyrénées-Orientales",
}

DOM_NAME_TO_CODE = {
    "Guadeloupe": "971",
    "Martinique": "972",
    "Guyane": "973",
    "La Réunion": "974",
    "Mayotte": "976",
}

# Dernier repli quand ni le champ pipeline ni le code postal du bénéficiaire ne permettent de
# rattacher un département (typiquement la Corse : cp_to_dept renvoie None pour tout code postal
# préfixé "20", ambigu entre 2A/2B) : mention explicite et non ambiguë d'une ville/du département
# dans le nom du bénéficiaire. Volontairement restreint aux cas évidents (préfectures, noms de
# département explicites) plutôt qu'une géolocalisation approximative de toutes les communes.
NAME_KEYWORDS_TO_DEPT = {
    "corse-du-sud": "2A",
    "corse du sud": "2A",
    "haute-corse": "2B",
    "haute corse": "2B",
    "ajaccio": "2A",
    "bastia": "2B",
    "porto-vecchio": "2A",
    "porto vecchio": "2A",
    "corte": "2B",
}


def _dept_from_name(nom_beneficiaire):
    if not nom_beneficiaire or not isinstance(nom_beneficiaire, str):
        return None
    nom_lower = nom_beneficiaire.lower()
    for keyword, dept in NAME_KEYWORDS_TO_DEPT.items():
        if keyword in nom_lower:
            return dept
    return None

DEPT_TO_REGION = {}
_REGIONS_DEPTS = {
    "Auvergne-Rhône-Alpes": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],
    "Bourgogne-Franche-Comté": ["21", "25", "39", "58", "70", "71", "89", "90"],
    "Bretagne": ["22", "29", "35", "56"],
    "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
    "Corse": ["2A", "2B"],
    "Grand Est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "Hauts-de-France": ["02", "59", "60", "62", "80"],
    "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "Normandie": ["14", "27", "50", "61", "76"],
    "Nouvelle-Aquitaine": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],
    "Occitanie": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],
    "Pays de la Loire": ["44", "49", "53", "72", "85"],
    "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
}
for _region, _depts in _REGIONS_DEPTS.items():
    for _dept in _depts:
        DEPT_TO_REGION[_dept] = _region


def _load_name_to_code():
    with open(DEPARTEMENTS_GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)
    name_to_code = {f["properties"]["nom"]: f["properties"]["code"] for f in geojson["features"]}
    name_to_code.update(DOM_NAME_TO_CODE)
    return name_to_code


NAME_TO_CODE = _load_name_to_code()


def load_departements_geojson():
    with open(DEPARTEMENTS_GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _normalize_numeric_code(code):
    if code.isdigit():
        if len(code) == 3 and code.startswith("0"):
            return code[1:]
        return code
    return code.upper().lstrip("0") or code.upper()


def parse_departement_field(raw):
    """Parse le champ "Département de l'opération". Deux formats coexistent dans les
    données : "CODE/Nom | CODE/Nom" (segments avec code explicite) et des segments sans
    code, listant un ou plusieurs noms séparés par des virgules ("Ain, Loire"). Retourne
    la liste des codes département identifiés (dédupliqués), ou [] si vide/non reconnu."""
    if not raw or not isinstance(raw, str):
        return []

    codes = []
    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if "/" in segment:
            code = segment.split("/", 1)[0].strip()
            codes.append(_normalize_numeric_code(code))
        else:
            for name in segment.split(","):
                name = name.strip()
                name = NAME_ALIASES.get(name, name)
                if name in NAME_TO_CODE:
                    codes.append(NAME_TO_CODE[name])

    return sorted(set(codes))


def cp_to_dept(code_postal):
    """Déduit le code département depuis un code postal français. Approximation : la
    Corse (préfixe "20") n'est pas résolue en 2A/2B à partir du seul code postal."""
    if not code_postal or not isinstance(code_postal, str):
        return None
    cp = code_postal.strip()
    if not cp.isdigit():
        return None
    cp = cp.zfill(5)
    if cp[:2] == "97":
        return cp[:3]
    if cp[:2] == "20":
        return None
    return cp[:2]


def assign_departments_df(df):
    """Ajoute les colonnes 'dept' et 'dept_source' à un DataFrame d'opérations."""
    df = df.copy()
    assigned = df.apply(assign_departement, axis=1)
    df["dept"], df["dept_source"] = zip(*assigned) if len(df) else ([], [])
    return df


DEPT_SOURCES = ("opération", "approximé", "nom du bénéficiaire", "inconnu")


def department_coverage_summary(df):
    """Part des opérations rattachées à un département via le champ pipeline (fiable),
    via approximation (code postal du bénéficiaire), via déduction du nom du bénéficiaire,
    ou non rattachées."""
    total = len(df)
    if not total:
        return {source: 0 for source in DEPT_SOURCES}
    counts = df["dept_source"].value_counts()
    return {source: counts.get(source, 0) / total for source in DEPT_SOURCES}


def assign_departement(op):
    """Rattache une opération à un département. Priorité au champ pipeline
    "Département de l'opération" quand il désigne un département unique (fiable) ;
    à défaut (champ vide, multi-département, ou non reconnu), approxime via le code
    postal du bénéficiaire (siège du bénéficiaire, pas nécessairement le lieu du projet) ;
    en dernier recours, déduit du nom du bénéficiaire quand il mentionne explicitement une
    ville/le département (cas de la Corse notamment, où le code postal seul ne permet pas de
    distinguer 2A/2B). Retourne (code_departement | None, source) avec source dans DEPT_SOURCES."""
    codes = parse_departement_field(op.get("Département de l’opération"))
    if len(codes) == 1:
        return codes[0], "opération"

    dept = cp_to_dept(op.get("Code postal du bénéficiaire"))
    if dept:
        return dept, "approximé"

    dept = _dept_from_name(op.get("Nom du bénéficiaire"))
    if dept:
        return dept, "nom du bénéficiaire"

    return None, "inconnu"


def build_department_choropleth(df_dept_assigned, region, amount_col="Montant UE"):
    """Carte des départements d'une région métropolitaine, colorée par montant UE total.
    df_dept_assigned doit déjà porter les colonnes 'dept'/'dept_source' (assign_departments_df)."""
    depts_region = [code for code, r in DEPT_TO_REGION.items() if r == region]
    geojson = load_departements_geojson()
    features = [f for f in geojson["features"] if f["properties"]["code"] in depts_region]
    filtered_geojson = {"type": "FeatureCollection", "features": features}

    agg = (
        df_dept_assigned[df_dept_assigned["dept"].isin(depts_region)]
        .groupby("dept")
        .agg(montant_ue_total=(amount_col, "sum"), count=(amount_col, "count"))
        .reset_index()
    )
    code_to_nom = {f["properties"]["code"]: f["properties"]["nom"] for f in features}
    agg["nom"] = agg["dept"].map(code_to_nom).fillna(agg["dept"])

    fig = px.choropleth(
        agg,
        geojson=filtered_geojson,
        locations="dept",
        featureidkey="properties.code",
        color="montant_ue_total",
        color_continuous_scale="Blues",
        custom_data=["nom", "count"],
        labels={"montant_ue_total": "Montant UE (€)"},
    )
    fig.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>Montant UE : %{z:,.0f} €<br>Nb projets : %{customdata[1]}<extra></extra>"
    )
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    return disable_map_interaction(style_map_background(style_hover(fig)))
