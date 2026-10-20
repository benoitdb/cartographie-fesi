"""Affichage par département : cartes, tableau et couverture du rattachement.

Le rattachement lui-même (colonnes `dept` et `dept_source`) est calculé par le
pipeline et écrit dans les Parquet (`data-pipeline/departements.py`, #232) : ce
module le lit, il ne le recalcule plus. Jusqu'à #232, la cascade vivait ici,
« propre à l'affichage » ; ADR 002 (étape 2) l'a déplacée pour que Metabase ait
aussi le département.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px

from utils.plot_style import disable_map_interaction, style_hover, style_map_background

# Seul import du pipeline : les libellés d'origine du rattachement, contrat entre
# ce qui les écrit et ce qui les affiche (#232). Une constante, un seul endroit.
# En fin de chemin : les modules du pipeline ne doivent masquer aucun autre.
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "data-pipeline"))
from departements import DEPT_SOURCES

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEPARTEMENTS_GEOJSON_PATH = REPO_ROOT / "data" / "geo" / "departements.geojson"

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


def load_departements_geojson():
    with open(DEPARTEMENTS_GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


NON_REPARTI = "Non réparti (région entière)"
HORS_PERIMETRE = "Hors périmètre (autre région)"


def tableau_departements(df_dept, region, montant_col="Montant UE"):
    """Tableau du « Détail par département » (pages 1 et 5, issue #157 écart D3) et échelle
    de couleur de la carte qui l'accompagne.

    `df_dept` : opérations de la région, avec la colonne `dept` écrite par le pipeline.
    Une ligne par département de la région, du plus doté au moins doté, puis deux lignes qui
    complètent le tableau à 100 % de la région (#100) : « Non réparti » (aucun département
    identifié) et « Hors périmètre » (département d'une autre région — siège du porteur,
    ou projet mené ailleurs). L'échelle ne voit que les vrais départements, les seuls
    dessinés sur la carte."""
    depts_region = {code for code, r in DEPT_TO_REGION.items() if r == region}
    connu = df_dept["dept"].notna()
    dans_region = connu & df_dept["dept"].isin(depts_region)
    tableau = (
        df_dept[dans_region]
        .groupby("dept")
        .agg(montant_ue_total=(montant_col, "sum"), count=(montant_col, "count"))
        .reset_index()
        .rename(columns={"dept": "Département", "montant_ue_total": "Montant UE total", "count": "Nb projets"})
        .sort_values("Montant UE total", ascending=False)
    )
    color_range = [0, tableau["Montant UE total"].max()] if len(tableau) else [0, 1]

    lignes_complementaires = [
        {"Département": libelle, "Montant UE total": df_dept.loc[masque, montant_col].sum(), "Nb projets": int(masque.sum())}
        for libelle, masque in ((NON_REPARTI, ~connu), (HORS_PERIMETRE, connu & ~dans_region))
        if masque.any()
    ]
    if lignes_complementaires:
        tableau = pd.concat([tableau, pd.DataFrame(lignes_complementaires)], ignore_index=True)
    return tableau, color_range


def department_coverage_summary(df):
    """Part des opérations rattachées à un département via le champ pipeline (fiable),
    via approximation (code postal du bénéficiaire), via déduction du nom du bénéficiaire,
    ou non rattachées."""
    total = len(df)
    if not total:
        return {source: 0 for source in DEPT_SOURCES}
    counts = df["dept_source"].value_counts()
    return {source: counts.get(source, 0) / total for source in DEPT_SOURCES}


def build_department_choropleth(df_dept_assigned, region, amount_col="Montant UE", show_colorbar=True, annotation=None):
    """Carte des départements d'une région métropolitaine, colorée par montant UE total.
    df_dept_assigned porte les colonnes 'dept'/'dept_source' écrites par le pipeline (#232).
    show_colorbar=False désactive la légende intégrée à la carte — à utiliser quand la carte est
    affichée à côté d'une légende autonome (build_standalone_colorbar) dans une colonne séparée,
    même principe que la carte nationale d'Accueil.py.
    annotation : texte court affiché en bas de la carte (survit à un screenshot, contrairement
    à un st.caption extérieur). Issue #92, piste 1."""
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
    bottom_margin = 30 if annotation else 0
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": bottom_margin}, coloraxis_showscale=show_colorbar)
    if annotation:
        fig.add_annotation(
            text=annotation,
            xref="paper", yref="paper",
            x=0.5, y=-0.02,
            showarrow=False,
            font=dict(size=11, color="#888"),
            xanchor="center", yanchor="top",
        )
    return disable_map_interaction(style_map_background(style_hover(fig)))


def build_dromcom_outline(territory, geojson, fill_color="#2a78d6"):
    """Contour réel d'un territoire DROM-COM unique, remplissage uni — pour la Vue Régionale
    d'un DROM-COM, où build_department_choropleth ne s'applique pas (chaque DROM-COM
    correspond à un département/collectivité unique, pas de découpage pertinent en dessous).
    Pas d'échelle de couleur par montant : un seul territoire affiché sur cette page, rien à
    comparer (contrairement aux vignettes DROM-COM d'Accueil.py, qui partagent une échelle
    nationale commune entre plusieurs territoires)."""
    fig = px.choropleth(
        pd.DataFrame([{"region": territory, "valeur": "valeur"}]),
        geojson=geojson,
        locations="region",
        featureidkey="properties.nom",
        color="valeur",
        color_discrete_map={"valeur": fill_color},
    )
    fig.update_traces(hovertemplate=f"<b>{territory}</b><extra></extra>")
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
    return disable_map_interaction(style_map_background(style_hover(fig)))


def build_dromcom_projects_map(territory, geojson, bubbles_df, amount_col="Montant UE", fill_color="#c9d9ec", bubble_color="#0ea5e9"):
    """Contour du territoire (rempli d'une couleur pâle, cf. build_dromcom_outline — Choropleth
    n'accepte pas de réglage d'opacité par trace, d'où une couleur claire plutôt qu'un fond
    foncé rendu transparent) avec une bulle par code postal regroupant les opérations qui s'y
    rattachent — taille proportionnelle au
    montant UE cumulé du groupe. Une seule couleur de bulle : la distinction opération réelle
    vs. bénéficiaire approximé est expliquée en caption (taux de couverture par source), pas
    encodée visuellement — un territoire DROM-COM est déjà petit à l'écran, une deuxième
    dimension de couleur surchargerait plus qu'elle n'informerait."""
    fig = px.choropleth(
        pd.DataFrame([{"region": territory, "valeur": "valeur"}]),
        geojson=geojson,
        locations="region",
        featureidkey="properties.nom",
        color="valeur",
        color_discrete_map={"valeur": fill_color},
    )
    fig.update_traces(hovertemplate=f"<b>{territory}</b><extra></extra>")
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")

    if len(bubbles_df):
        montant_max = bubbles_df[amount_col].max()
        fig.add_scattergeo(
            lon=bubbles_df["lon"],
            lat=bubbles_df["lat"],
            text=bubbles_df["commune"],
            customdata=bubbles_df[["code_postal", "count", amount_col]],
            mode="markers",
            marker=dict(
                size=bubbles_df[amount_col],
                sizemode="area",
                sizeref=2.0 * montant_max / (40.0**2) if montant_max else 1,
                color=bubble_color,
                opacity=0.8,
                line=dict(width=1, color="white"),
            ),
            hovertemplate=(
                "<b>%{text}</b> (%{customdata[0]})<br>%{customdata[1]} projet(s)<br>"
                "Montant UE : %{customdata[2]:,.0f} €<extra></extra>"
            ),
        )

    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
    return disable_map_interaction(style_map_background(style_hover(fig)))
