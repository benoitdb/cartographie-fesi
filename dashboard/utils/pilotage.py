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


def render_kpi_pilotage(df_fonds_pilotage, montant_programme, montant_engage):
    """Bloc A : montants agrégés (programmé, engagé, reste à engager) + une card par fonds
    avec sa propre barre de progression. N'affiche rien si aucune donnée programmée pour ce
    périmètre (ex. fonds sélectionnés absents du Tableau 9B).

    Le reste à engager agrégé est la somme des restes PAR FONDS (chacun plancher à 0), pas
    programme_total - engage_total : un fonds en dépassement (ex. FSE+, voir
    FSE_DEPASSEMENT_DETAIL) ne doit jamais "rogner" sur le reste d'un autre fonds dans ce
    total — sinon un dépassement FSE+ peut faire disparaître un vrai reliquat FEDER du total
    affiché (cas constaté : Auvergne-Rhône-Alpes affichait 94% consommé au global alors qu'il
    restait ~150M€ de FEDER, le dépassement FSE+ masquant ce reliquat dans l'agrégat)."""
    if not montant_programme or df_fonds_pilotage.empty:
        return

    reste = (df_fonds_pilotage["programme"] - df_fonds_pilotage["engage"]).clip(lower=0).sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown(f"**Programmé 2021-2027 :** {montant_programme / 1e6:,.1f} M€".replace(",", " "))
    with col2:
        with st.container(border=True):
            st.markdown(f"**Engagé :** {montant_engage / 1e6:,.1f} M€".replace(",", " "))
    with col3:
        with st.container(border=True):
            st.markdown(f"**Reste à engager (est.) :** {reste / 1e6:,.1f} M€".replace(",", " "))
    st.caption(RESERVE_METHODO)

    depassement_present = False
    fonds_cols = st.columns(len(df_fonds_pilotage))
    for col, row in zip(fonds_cols, df_fonds_pilotage.itertuples()):
        taux_fonds = row.engage / row.programme if row.programme else 0
        depassement = taux_fonds > 1
        depassement_present = depassement_present or depassement
        with col:
            with st.container(border=True):
                st.markdown(
                    f"**{row.fonds} :** {row.engage / 1e6:,.1f} / {row.programme / 1e6:,.1f} M€".replace(",", " ")
                )
                st.plotly_chart(
                    build_fonds_mini_bar(row.engage, row.programme),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
                st.caption(f"⚠️ {taux_fonds:.0%} — dépassement" if depassement else f"{taux_fonds:.0%} consommé")
    if depassement_present:
        st.caption(FSE_DEPASSEMENT_DETAIL)


def build_fonds_mini_bar(engage, programme):
    """Mini barre de progression (une card = un fonds, dans render_kpi_pilotage) : st.progress
    plafonne visuellement à 100% et ne peut pas se colorer, donc barre Plotly custom à la
    place — la barre engagée dépasse visuellement le repère "Programmé" (ligne pointillée
    verticale) en cas de dépassement, colorée en rouge plutôt que tronquée à 100%, pour que le
    dépassement (voir FSE_DEPASSEMENT_DETAIL) reste visible plutôt que caché par le plafond."""
    taux = engage / programme if programme else 0
    depassement = taux > 1
    color = "#e34948" if depassement else "#4C78A8"
    x_max = max(engage, programme) * 1.15 if programme else engage * 1.15

    fig = go.Figure()
    fig.add_bar(
        x=[engage],
        y=[""],
        orientation="h",
        marker_color=color,
        text=[f"{taux:.0%} ⚠️" if depassement else f"{taux:.0%}"],
        textposition="outside",
        hovertemplate=f"Engagé : {engage:,.0f} €<br>Programmé : {programme:,.0f} €<extra></extra>".replace(",", " "),
        showlegend=False,
    )
    fig.add_vline(x=programme, line_dash="dash", line_color="#555", line_width=2)
    fig.update_layout(
        height=70,
        margin=dict(l=0, r=45, t=10, b=0),
        xaxis=dict(range=[0, x_max], visible=False),
        yaxis=dict(visible=False),
    )
    return style_hover(fig)


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
