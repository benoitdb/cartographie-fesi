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


def reste_a_engager(df_fonds_pilotage):
    """Somme des restes à engager **par fonds**, chacun plancher à zéro.

    Surtout pas `programme_total - engage_total` : un fonds en dépassement (voir
    FSE_DEPASSEMENT_DETAIL) rognerait alors le reliquat des autres. Cas constaté qui a
    motivé la règle : Auvergne-Rhône-Alpes affichait 94% consommé au global alors qu'il
    restait ~150 M€ de FEDER, le dépassement FSE+ masquant ce reliquat dans l'agrégat.

    Fonction à part plutôt qu'une ligne dans le rendu (issue #62) : c'est une règle
    métier, elle se teste sans passer par l'affichage.
    """
    return (df_fonds_pilotage["programme"] - df_fonds_pilotage["engage"]).clip(lower=0).sum()


def taux_consommation(engage, programme):
    """Part de l'enveloppe programmée déjà engagée, 0 si rien n'est programmé.

    Peut dépasser 1 : le dépassement est un signal à afficher, pas une valeur à
    plafonner (voir FSE_DEPASSEMENT_DETAIL et build_fonds_mini_bar)."""
    return engage / programme if programme else 0


def render_kpi_pilotage(df_fonds_pilotage, montant_programme, montant_engage, ftj_article=None,
                       assistance_technique=None, color_map=None, libelle_programme="Programmé 2021-2027",
                       reserve_methodo=None, mention_depassement=None):
    """Bloc A : montants agrégés (programmé, engagé, reste à engager) + une card par fonds
    avec sa propre barre de progression. N'affiche rien si aucune donnée programmée pour ce
    périmètre (ex. fonds sélectionnés absents du Tableau 9B).

    Le reste à engager agrégé vient de reste_a_engager() : somme des restes PAR FONDS,
    chacun plancher à 0 — voir la docstring de cette fonction pour le pourquoi.

    ftj_article (optionnel) : {"Article 3": montant, "Article 4": montant} programmés pour ce
    périmètre — classification propre au FTJ (règlement FTJ), sans lien avec les 3 catégories
    de cohésion FEDER/FSE+, affichée en complément sous la card FTJ (issues #20/#21).

    assistance_technique (optionnel) : {fonds: montant} des enveloppes d'assistance technique
    par fonds pour ce périmètre — budget de soutien à l'instruction/gestion des programmes,
    distinct des montants programmés/engagés ci-dessus (ni programmé aux porteurs de projet,
    ni comparable à un "engagé"), affiché à part pour ne pas fausser le taux de consommation
    (issues #20/#21).

    libelle_programme / reserve_methodo / mention_depassement (optionnels) : les textes qui
    dépendent de la période. Leur valeur par défaut est celle de 2021-2027, pour que les
    trois pages de cette période appellent la fonction sans rien changer ; la page
    2014-2020 passe les siennes (l'enveloppe n'a ni la même date, ni la même provenance,
    ni la même raison de déborder — voir utils.periodes). Le libellé était écrit en dur
    ici, ce qui aurait fait afficher « Programmé 2021-2027 » au-dessus de chiffres de
    2014-2020 (issue #93).

    color_map (optionnel) : {valeur de df_fonds_pilotage["fonds"]: couleur}, ex. FONDS_COLORS
    ou OBJECTIF_STRATEGIQUE_COLORS (themes.py) — réutilise cette fonction pour une dimension
    autre que le Fonds (ex. pilotage par Objectif Stratégique, issue #21) avec des couleurs
    cohérentes avec les autres graphes de la même dimension. None conserve la couleur par
    défaut (bleu, rouge si dépassement)."""
    if not montant_programme or df_fonds_pilotage.empty:
        return

    reste = reste_a_engager(df_fonds_pilotage)

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown(f"**{libelle_programme} :** {montant_programme / 1e6:,.1f} M€".replace(",", " "))
    with col2:
        with st.container(border=True):
            st.markdown(f"**Engagé :** {montant_engage / 1e6:,.1f} M€".replace(",", " "))
    with col3:
        with st.container(border=True):
            st.markdown(f"**Reste à engager (est.) :** {reste / 1e6:,.1f} M€".replace(",", " "))
    st.caption(reserve_methodo or RESERVE_METHODO)

    depassement_present = False
    fonds_cols = st.columns(len(df_fonds_pilotage))
    for col, row in zip(fonds_cols, df_fonds_pilotage.itertuples(), strict=True):
        taux_fonds = taux_consommation(row.engage, row.programme)
        depassement = taux_fonds > 1
        depassement_present = depassement_present or depassement
        with col:
            with st.container(border=True):
                st.markdown(
                    f"**{row.fonds} :** {row.engage / 1e6:,.1f} / {row.programme / 1e6:,.1f} M€".replace(",", " ")
                )
                st.plotly_chart(
                    build_fonds_mini_bar(row.engage, row.programme, color=(color_map or {}).get(row.fonds)),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
                st.caption(f"⚠️ {taux_fonds:.0%} — dépassement" if depassement else f"{taux_fonds:.0%} consommé")
                # Ligne toujours présente (même vide) sur chaque card : le détail Article 3/4 ne
                # concerne que le FTJ, mais laisser les autres cards sans cette ligne les rendait
                # plus basses — un espace insécable réserve la même hauteur sans rien afficher.
                if row.fonds == "FTJ" and ftj_article:
                    art3, art4 = ftj_article.get("Article 3", 0), ftj_article.get("Article 4", 0)
                    st.caption(f"dont Article 3 : {art3 / 1e6:,.1f} M€ · Article 4 : {art4 / 1e6:,.1f} M€".replace(",", " "))
                else:
                    st.caption(" ")
    if depassement_present:
        st.caption(mention_depassement or FSE_DEPASSEMENT_DETAIL)
    if assistance_technique:
        detail_at = ", ".join(f"{f} {v / 1e6:,.1f} M€".replace(",", " ") for f, v in assistance_technique.items())
        st.caption(
            f"+ Assistance technique programmée (hors montants ci-dessus, budget de soutien à "
            f"l'instruction/gestion des programmes) : {detail_at}."
        )


def build_fonds_mini_bar(engage, programme, color=None):
    """Mini barre de progression (une card = un fonds, dans render_kpi_pilotage) : st.progress
    plafonne visuellement à 100% et ne peut pas se colorer, donc barre Plotly custom à la
    place — la barre engagée dépasse visuellement le repère "Programmé" (ligne pointillée
    verticale) en cas de dépassement, colorée en rouge plutôt que tronquée à 100%, pour que le
    dépassement (voir FSE_DEPASSEMENT_DETAIL) reste visible plutôt que caché par le plafond.

    color (optionnel) : couleur de la catégorie (ex. OBJECTIF_STRATEGIQUE_COLORS), pour rester
    cohérent avec les autres graphes de la même dimension — le rouge de dépassement reste
    toujours prioritaire dessus, c'est un signal d'alerte, pas une couleur de catégorie."""
    taux = taux_consommation(engage, programme)
    depassement = taux > 1
    color = "#e34948" if depassement else (color or "#4C78A8")
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
    text_labels = [f"{t:.0%} ⚠️" if d else f"{t:.0%}" for t, d in zip(taux, depassement, strict=True)]

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
