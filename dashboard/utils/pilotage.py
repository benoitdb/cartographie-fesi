import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.plot_style import style_hover

# Bornes de la programmation 2021-2027, pour un rythme linéaire de référence (build_trajectoire).
PERIODE_DEBUT = pd.Timestamp("2021-01-01")
PERIODE_FIN = pd.Timestamp("2027-12-31")

RESERVE_METHODO = (
    "⚠️ Le montant programmé provient de l'Accord de partenariat 2021-2027 (tableau des "
    "dotations financières **préliminaires**, version adoptée le 2 juin 2022) — les "
    "programmes ont probablement été révisés depuis (reprogrammations), donc le taux de "
    "consommation ci-dessous est une estimation, pas un chiffre d'exécution officiel."
)

FSE_DEPASSEMENT_DETAIL = (
    "⚠️ Une barre rouge signale un taux > 100% pour le FSE+ : un mécanisme de transfert "
    "national → régional (non tracé dans nos données, voir Accord de partenariat) fait que "
    "l'enveloppe FSE+ propre d'une région ne couvre pas tout ce qu'elle engage réellement — "
    "le dépassement est donc un signal de ce transfert, pas une anomalie de données."
)


def render_kpi_pilotage(montant_engage, montant_programme):
    """Bloc A : % consommé global (tous fonds) + reste à engager. N'affiche rien si aucune
    donnée programmée pour ce périmètre (ex. fonds sélectionnés absents du Tableau 9B)."""
    if not montant_programme:
        return

    taux = montant_engage / montant_programme
    reste = max(montant_programme - montant_engage, 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with st.container(border=True):
            st.markdown(f"**Programmé 2021-2027 :** {montant_programme / 1e6:,.1f} M€".replace(",", " "))
    with col2:
        with st.container(border=True):
            st.markdown(f"**Engagé :** {montant_engage / 1e6:,.1f} M€".replace(",", " "))
    with col3:
        with st.container(border=True):
            st.markdown(f"**% consommé :** {taux:.0%}")
    with col4:
        with st.container(border=True):
            st.markdown(f"**Reste à engager (est.) :** {reste / 1e6:,.1f} M€".replace(",", " "))
    st.progress(min(taux, 1.0))
    st.caption(RESERVE_METHODO)


def build_trajectoire(df_ops, montant_programme, amount_col="Montant UE", date_col="Date de début de l'opération"):
    """Bloc C : courbe cumulée réelle + rythme linéaire de référence (montant programmé
    réparti uniformément sur 2021-2027) — visualise l'avance ou le retard d'engagement par
    rapport à un rythme régulier."""
    plot_df = df_ops[[date_col, amount_col]].copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col])
    plot_df = plot_df.groupby(date_col, as_index=False)[amount_col].sum().sort_values(date_col)
    plot_df["cumule"] = plot_df[amount_col].cumsum()

    fig = go.Figure()
    fig.add_scatter(
        x=plot_df[date_col],
        y=plot_df["cumule"],
        mode="lines",
        name="Engagé (réel)",
        line=dict(width=2),
        hovertemplate="%{x|%d/%m/%Y}<br>Cumulé réel : %{y:,.0f} €<extra></extra>",
    )
    if montant_programme:
        fig.add_scatter(
            x=[PERIODE_DEBUT, PERIODE_FIN],
            y=[0, montant_programme],
            mode="lines",
            name="Rythme linéaire de référence",
            line=dict(width=1, dash="dot", color="gray"),
            hovertemplate="Rythme linéaire attendu<br>%{y:,.0f} €<extra></extra>",
        )
    fig.update_layout(yaxis_title="Montant UE cumulé (€)", legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_hover(fig)


def build_ranking_programme_vs_engage(df, label_col, engage_col, programme_col, height=None):
    """Bullet chart d'un ensemble de catégories (régions, ou fonds au sein d'une région) :
    barre de fond = programmé (pleine longueur), barre superposée = engagé, triées par
    montant programmé décroissant — l'écart visuel entre les deux extrémités de barre EST le
    reste à engager, pas besoin d'une 3e série. % consommé en étiquette au bout de la barre
    engagée. height : calculé selon le nombre de lignes si non fourni (utile pour une petite
    liste, ex. FEDER/FTJ, où la hauteur par défaut serait disproportionnée).

    Une catégorie dont l'engagé dépasse le programmé (ex. FSE+, voir FSE_DEPASSEMENT_DETAIL)
    est affichée en rouge plutôt que masquée — le dépassement est un signal à part entière,
    pas une anomalie à cacher."""
    df = df.sort_values(programme_col)
    taux = df[engage_col] / df[programme_col]
    depassement = taux > 1
    engage_colors = ["#e34948" if d else "#4C78A8" for d in depassement]
    text_labels = [f"{t:.0%} ⚠️" if d else f"{t:.0%}" for t, d in zip(taux, depassement)]

    fig = go.Figure()
    fig.add_bar(
        x=df[programme_col],
        y=df[label_col],
        orientation="h",
        name="Programmé",
        marker_color="#c8d4e3",
        hovertemplate="<b>%{y}</b><br>Programmé : %{x:,.0f} €<extra></extra>",
    )
    fig.add_bar(
        x=df[engage_col],
        y=df[label_col],
        orientation="h",
        name="Engagé",
        marker_color=engage_colors,
        text=text_labels,
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Engagé : %{x:,.0f} €<br>% consommé : %{text}<extra></extra>",
    )
    if depassement.any():
        fig.add_scatter(
            x=[None], y=[None], mode="markers", marker=dict(color="#e34948", symbol="square"), name="Dépassement (> programmé)"
        )

    fig.update_layout(
        barmode="overlay",
        height=height if height else max(400, 35 * len(df)),
        xaxis_title="Montant UE (€)",
        yaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return style_hover(fig)
