import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")

data = load_data()
by_region = data["aggregates"]["by_region"]
by_region_fonds = data["aggregates"]["by_region_fonds"]

# "Volet national" n'est pas une région géographique : listé à part, en fin de sélecteur
regions = sorted(r for r in by_region if r != "Volet national") + ["Volet national"]

region = st.selectbox("Région", regions)

st.title(f"Vue Régionale - {region}")

region_data = by_region[region]

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{region_data['count']:,}".replace(",", " "))
col3.metric("Montant UE moyen", f"{region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))

# Répartition par fonds
st.subheader("Répartition par fonds")

df_region_fonds = pd.DataFrame(
    [
        {"fonds": v["fonds"], "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
        for key, v in by_region_fonds.items()
        if v["region"] == region
    ]
).sort_values("montant_ue_total")

fig_region_fonds = px.bar(
    df_region_fonds,
    x="montant_ue_total",
    y="fonds",
    orientation="h",
    color="fonds",
    hover_data=["count"],
    labels={"montant_ue_total": "Montant UE (€)", "fonds": "Fonds", "count": "Nb projets"},
)
fig_region_fonds.update_layout(height=250, showlegend=False)
fig_region_fonds.update_traces(width=0.5)

st.plotly_chart(fig_region_fonds, use_container_width=True)

# Objectifs : stratégique > spécifique > type d'intervention
st.subheader("Objectifs stratégiques, spécifiques et types d'intervention")

if region == "Volet national":
    region_ops = [op for op in data["operations"] if op.get("is_national")]
else:
    region_ops = [
        op
        for op in data["operations"]
        if op.get("regions_modernes") == [region] and not op.get("is_interregional") and not op.get("is_national")
    ]

df_region_ops = pd.DataFrame(region_ops)
df_region_ops["Objectif stratégique"] = df_region_ops["Objectif stratégique"].fillna("Non spécifié")
df_region_ops["Objectif spécifique (Code et libellé)"] = df_region_ops["Objectif spécifique (Code et libellé)"].fillna(
    "Non spécifié"
)
df_region_ops["Type d'intervention"] = df_region_ops["Type d'intervention"].fillna("Non spécifié")

LEVEL1, LEVEL2, LEVEL3 = "Objectif stratégique", "Objectif spécifique (Code et libellé)", "Type d'intervention"
SEP = "|||"  # séparateur d'id peu susceptible d'apparaître dans les libellés (contrairement à "/")


def format_montant(x):
    return f"{x:,.0f} €".replace(",", " ")


def wrap_label(text, width=40):
    return "<br>".join(textwrap.wrap(text, width=width, break_long_words=False))


# Agrégats à chaque niveau, pour que les totaux au survol soient corrects
# (Plotly agrège automatiquement "value", mais pas les colonnes customdata)
agg_l1 = df_region_ops.groupby(LEVEL1).agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count")).reset_index()
agg_l2 = (
    df_region_ops.groupby([LEVEL1, LEVEL2])
    .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
    .reset_index()
)
agg_l3 = (
    df_region_ops.groupby([LEVEL1, LEVEL2, LEVEL3])
    .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
    .reset_index()
)

ids, labels, parents, values, montants_affiches, counts, hover_labels = [], [], [], [], [], [], []

for _, row in agg_l1.iterrows():
    ids.append(row[LEVEL1])
    labels.append(row[LEVEL1])
    parents.append("")
    values.append(row["montant_ue_total"])
    montants_affiches.append(format_montant(row["montant_ue_total"]))
    counts.append(row["count"])
    hover_labels.append(wrap_label(row[LEVEL1]))

for _, row in agg_l2.iterrows():
    ids.append(f"{row[LEVEL1]}{SEP}{row[LEVEL2]}")
    labels.append(row[LEVEL2])
    parents.append(row[LEVEL1])
    values.append(row["montant_ue_total"])
    montants_affiches.append(format_montant(row["montant_ue_total"]))
    counts.append(row["count"])
    hover_labels.append(wrap_label(row[LEVEL2]))

for _, row in agg_l3.iterrows():
    parent_id = f"{row[LEVEL1]}{SEP}{row[LEVEL2]}"
    ids.append(f"{parent_id}{SEP}{row[LEVEL3]}")
    labels.append(row[LEVEL3])
    parents.append(parent_id)
    values.append(row["montant_ue_total"])
    montants_affiches.append(format_montant(row["montant_ue_total"]))
    counts.append(row["count"])
    hover_labels.append(wrap_label(row[LEVEL3]))

# Couleur cohérente par objectif stratégique, propagée à tous ses descendants
palette = px.colors.qualitative.Plotly
color_map = {cat: palette[i % len(palette)] for i, cat in enumerate(agg_l1[LEVEL1])}
colors = [color_map[node_id.split(SEP)[0]] for node_id in ids]

fig_hierarchy = go.Figure(
    go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        marker=dict(colors=colors),
        customdata=list(zip(montants_affiches, counts, hover_labels)),
        texttemplate="%{label}<br>%{value:,.0f} €",
        hovertemplate="<b>%{customdata[2]}</b><br>Montant UE : %{customdata[0]}<br>Nb projets : %{customdata[1]}<extra></extra>",
    )
)
fig_hierarchy.update_layout(
    hoverlabel=dict(align="left", font=dict(size=13, color="#1a1a1a"), bgcolor="white")
)

st.plotly_chart(fig_hierarchy, use_container_width=True)

# Courbe cumulée d'engagement UE dans le temps
st.subheader("Engagement UE cumulé dans le temps")
st.caption(
    "Basé sur la date de début de l'opération. Environ 60% des dates sont arrondies au 1ᵉʳ janvier "
    "(date administrative/programmatique plutôt qu'une date de démarrage individuelle précise) : "
    "la courbe présente donc des paliers plutôt qu'une progression lissée."
)

st.caption("Cliquer sur un fonds dans la légende pour l'isoler ou le masquer.")

df_dates = df_region_ops[["Date de début de l'opération", "Montant UE", "Fonds"]].copy()
df_dates["Date de début de l'opération"] = pd.to_datetime(df_dates["Date de début de l'opération"])
df_dates = (
    df_dates.groupby(["Fonds", "Date de début de l'opération"], as_index=False)["Montant UE"]
    .sum()
    .sort_values(["Fonds", "Date de début de l'opération"])
)
df_dates["cumule"] = df_dates.groupby("Fonds")["Montant UE"].cumsum()

fig_cumul = px.line(
    df_dates,
    x="Date de début de l'opération",
    y="cumule",
    color="Fonds",
    labels={"Date de début de l'opération": "Date", "cumule": "Montant UE cumulé (€)"},
)
fig_cumul.update_traces(line=dict(width=2))

for year in range(
    df_dates["Date de début de l'opération"].dt.year.min(), df_dates["Date de début de l'opération"].dt.year.max() + 1
):
    fig_cumul.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)

st.plotly_chart(fig_cumul, use_container_width=True)
