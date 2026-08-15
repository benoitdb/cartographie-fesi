import textwrap

import plotly.graph_objects as go


def wrap_label(text, width=40):
    """Insère des retours à la ligne dans un libellé long (les valeurs brutes du champ
    'Objectif stratégique'/'Type d'intervention' etc. peuvent être longues), pour l'affichage
    dans les hovers et les treemaps."""
    return "<br>".join(textwrap.wrap(str(text), width=width, break_long_words=False))


def format_montant(x):
    return f"{x:,.0f} €".replace(",", " ")


def style_hover(fig):
    """Force un hover lisible (texte foncé sur fond blanc fixe), quel que soit le thème
    Streamlit (clair/sombre) — sans ce réglage, le hoverlabel hérite des couleurs du thème
    et peut devenir illisible (texte clair sur fond clair en mode sombre)."""
    fig.update_layout(hoverlabel=dict(align="left", font=dict(size=13, color="#1a1a1a"), bgcolor="white"))
    return fig


def style_map_background(fig):
    """Rend transparents le fond de la carte (subplot geo) et le fond de la figure — par défaut
    Plotly les affiche en blanc opaque, ce qui ressort comme un rectangle blanc en mode sombre."""
    fig.update_geos(bgcolor="rgba(0,0,0,0)", lakecolor="rgba(0,0,0,0)")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def disable_map_interaction(fig):
    """Désactive le pan (glisser-déposer) sur une carte choropleth — gênant en usage normal
    (la carte n'a pas besoin d'être déplacée, toujours cadrée sur ses features via fitbounds).
    À utiliser avec MAP_CONFIG (scroll-to-zoom, molette qui interfère avec le défilement de la
    page) passé au paramètre config de st.plotly_chart pour ce même graphique."""
    fig.update_layout(dragmode=False)
    return fig


# À passer explicitement au paramètre config= de st.plotly_chart pour toute carte choropleth
# (config n'est pas un réglage de la figure, donc ne peut pas être fixé dans le builder).
MAP_CONFIG = {"scrollZoom": False}


def build_standalone_colorbar(color_range, title, height=450, colorscale="Blues"):
    """Barre de couleur seule, sans carte attachée — pour afficher une légende de couleur
    partagée par plusieurs cartes côte à côte dans des colonnes Streamlit séparées (une figure
    Plotly ne peut pas être scindée entre deux colonnes, donc chaque carte doit désactiver son
    propre colorbar via coloraxis_showscale=False et cette légende autonome les remplace toutes).
    Trace factice invisible (marker sans point affiché) portant uniquement le colorbar,
    technique standard Plotly pour une légende sans donnée à tracer."""
    fig = go.Figure(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(
                colorscale=colorscale,
                cmin=color_range[0],
                cmax=color_range[1],
                color=[color_range[0]],
                showscale=True,
                colorbar=dict(title=title, tickformat=",.0f", len=0.9, thickness=15, x=0, xanchor="left"),
            ),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=height,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
