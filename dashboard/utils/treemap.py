import plotly.express as px
import plotly.graph_objects as go

from utils.plot_style import format_montant, style_hover, wrap_label

SEP = "|||"  # séparateur d'id peu susceptible d'apparaître dans les libellés (contrairement à "/")


def build_hierarchy_treemap(df, level_cols, amount_col="Montant UE", color_map=None):
    """Treemap N niveaux avec agrégats explicites à chaque niveau (nécessaire pour
    un hover correct sur les nœuds parents, que px.treemap ne calcule pas nativement).
    Couleur attribuée par catégorie du niveau racine (level_cols[0]), propagée aux descendants.
    Si color_map est fourni, ces couleurs priment (catégories absentes du mapping : palette
    de repli) — pour une identité visuelle fixe (ex. thèmes des objectifs stratégiques).
    """
    ids, labels, parents, values, montants_affiches, counts, hover_labels = [], [], [], [], [], [], []

    for i in range(1, len(level_cols) + 1):
        cols = level_cols[:i]
        agg = df.groupby(cols).agg(montant_ue_total=(amount_col, "sum"), count=(amount_col, "count")).reset_index()
        for _, row in agg.iterrows():
            path_values = [str(row[c]) for c in cols]
            node_id = SEP.join(path_values)
            parent_id = SEP.join(path_values[:-1]) if i > 1 else ""
            ids.append(node_id)
            labels.append(path_values[-1])
            parents.append(parent_id)
            values.append(row["montant_ue_total"])
            montants_affiches.append(format_montant(row["montant_ue_total"]))
            counts.append(row["count"])
            hover_labels.append(wrap_label(path_values[-1]))

    top_level_values = df[level_cols[0]].unique()
    palette = px.colors.qualitative.Plotly
    fallback_map = {cat: palette[i % len(palette)] for i, cat in enumerate(top_level_values)}
    resolved_map = {cat: (color_map or {}).get(cat, fallback_map[cat]) for cat in top_level_values}
    colors = [resolved_map[node_id.split(SEP)[0]] for node_id in ids]

    fig = go.Figure(
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
    return style_hover(fig)
