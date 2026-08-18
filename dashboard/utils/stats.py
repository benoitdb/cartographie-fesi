import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils.plot_style import format_montant, style_hover, wrap_label
from utils.table_style import text_widths


def _concentration_top10(montants):
    """Part du montant total portée par les 10% de projets les plus importants du groupe
    (mesure de concentration du portefeuille : quelques gros projets vs. une répartition
    diffuse)."""
    montants_tries = montants.sort_values(ascending=False)
    total = montants_tries.sum()
    if not total:
        return 0.0
    n_top = max(1, round(len(montants_tries) * 0.1))
    return montants_tries.iloc[:n_top].sum() / total


def compute_stats_table(df, group_col, amount_col="Montant UE"):
    """Médiane, écart-type, coefficient de variation et concentration des montants,
    par catégorie de group_col.

    Le coefficient de variation (écart-type / médiane) rend l'écart-type comparable entre
    groupes d'échelles très différentes (ex. FTJ vs FEDER), ce que l'écart-type brut ne
    permet pas.
    """
    agg = df.groupby(group_col)[amount_col].agg(mediane="median", ecart_type="std", count="count").reset_index()
    agg["ecart_type"] = agg["ecart_type"].fillna(0)
    agg["cv"] = (agg["ecart_type"] / agg["mediane"]).replace([float("inf")], 0).fillna(0)

    concentration = df.groupby(group_col)[amount_col].apply(_concentration_top10).reset_index(name="concentration_top10")
    agg = agg.merge(concentration, on=group_col)

    return agg.sort_values("mediane", ascending=False)


def _iqr_outlier_mask(df, amount_col):
    q1, q3 = df[amount_col].quantile(0.25), df[amount_col].quantile(0.75)
    iqr = q3 - q1
    borne_basse, borne_haute = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return (df[amount_col] < borne_basse) | (df[amount_col] > borne_haute)


def detect_outliers(df, amount_col="Montant UE", group_col=None):
    """Opérations dont le montant sort de [Q1 - 1.5*IQR, Q3 + 1.5*IQR].

    group_col (optionnel, ex. "Fonds") : calcule les bornes séparément par groupe plutôt que sur
    l'ensemble du périmètre passé. Sans ça, un fonds à plus grande échelle (FEDER, médiane ~250k€)
    fait paraître ses projets normaux "atypiques" simplement parce qu'ils sont comparés à des
    fonds à plus petite échelle (FSE+, médiane ~96k€) — confirmé sur les données nationales :
    540 opérations (dont 502 FEDER) étaient signalées à tort par une borne unique, alors que
    normales au sein de leur propre fonds.
    """
    if group_col is None:
        mask = _iqr_outlier_mask(df, amount_col)
    else:
        mask = pd.Series(False, index=df.index)
        for _, groupe in df.groupby(group_col):
            mask.loc[groupe.index] = _iqr_outlier_mask(groupe, amount_col)
    return df[mask].sort_values(amount_col, ascending=False)


def build_histogram(df, amount_col="Montant UE", nbins=50, log_x=False, color_col=None, color_map=None):
    """Histogramme des montants, empilé par color_col si fourni. En échelle logarithmique
    (recommandé pour ces données, fortement asymétriques : une majorité de petites opérations
    et une minorité de très gros projets), les bins sont calculés en espace log pour rester
    réguliers à l'affichage. color_map (optionnel) fixe la couleur par catégorie plutôt que
    la palette par défaut."""
    plot_df = df
    x_col = amount_col
    if log_x:
        plot_df = df[df[amount_col] > 0].copy()
        x_col = f"log_{amount_col}"
        plot_df[x_col] = plot_df[amount_col].apply(math.log10)

    fig = px.histogram(
        plot_df,
        x=x_col,
        color=color_col,
        color_discrete_map=color_map,
        barmode="stack",
        nbins=nbins,
        labels={x_col: "Montant UE (€)"},
    )
    if log_x:
        tickvals = list(range(0, 9))
        fig.update_xaxes(
            tickvals=tickvals,
            ticktext=[f"{10**v:,.0f} €".replace(",", " ") for v in tickvals],
        )
    fig.update_layout(yaxis_title="Nombre d'opérations", bargap=0.05)
    fig.for_each_trace(
        lambda t: t.update(
            hovertemplate=f"<b>{wrap_label(t.name) if t.name else 'Opérations'}</b><br>Nb opérations : %{{y:,.0f}}<extra></extra>"
        )
    )
    return style_hover(fig)


def build_boxplot(df, group_col, amount_col="Montant UE", log_y=False, color_map=None):
    """Box plot (médiane, quartiles/IQR, outliers) des montants par groupe — visualisation
    directe de ce que présente compute_stats_table. Échelle log recommandée vu l'asymétrie
    des montants (sinon les boîtes des groupes à petits montants sont écrasées par les outliers).
    color_map (optionnel) fixe la couleur par catégorie plutôt que la palette par défaut."""
    fig = px.box(
        df,
        x=group_col,
        y=amount_col,
        color=group_col,
        color_discrete_map=color_map,
        points="outliers",
        labels={amount_col: "Montant UE (€)"},
    )
    fig.update_layout(showlegend=False)
    if log_y:
        fig.update_yaxes(type="log")
    fig.for_each_trace(
        lambda t: t.update(hovertemplate=f"<b>{wrap_label(t.name)}</b><br>Montant UE : %{{y:,.0f}} €<extra></extra>")
    )
    return style_hover(fig)


def build_portfolio_scatter(df, group_col, amount_col="Montant UE"):
    """Structure du portefeuille par groupe : nombre de projets (x) vs montant UE moyen (y),
    taille de bulle = montant total — distingue les groupes à peu de gros projets de ceux
    à beaucoup de petits projets."""
    agg = df.groupby(group_col)[amount_col].agg(count="count", montant_moyen="mean", montant_total="sum").reset_index()
    fig = px.scatter(
        agg,
        x="count",
        y="montant_moyen",
        size="montant_total",
        color=group_col,
        hover_name=group_col,
        labels={"count": "Nombre de projets", "montant_moyen": "Montant UE moyen (€)", "montant_total": "Montant UE total (€)"},
    )
    fig.update_layout(showlegend=False)
    fig.for_each_trace(
        lambda t: t.update(
            hovertemplate=(
                f"<b>{wrap_label(t.name)}</b><br>Nombre de projets : %{{x}}<br>"
                "Montant UE moyen : %{y:,.0f} €<br>Montant UE total : %{marker.size:,.0f} €<extra></extra>"
            )
        )
    )
    return style_hover(fig)


def build_portfolio_scatter_comparison(df, group_col, theme_col, amount_col="Montant UE", color_map=None):
    """Deux scatterplots (montant UE moyen | montant UE total) côte à côte dans une seule figure,
    avec une légende unique horizontale en bas (les deux graphiques partagent la même dimension
    couleur). Chaque bulle est une combinaison (group_col, theme_col), dimensionnée par montant UE
    total, colorée par theme_col (objectif stratégique) — pour repérer si une thématique concentre
    l'essentiel de la valeur sur certains groupes."""
    agg = df.groupby([group_col, theme_col])[amount_col].agg(count="count", montant_moyen="mean", montant_total="sum").reset_index()
    themes = sorted(agg[theme_col].unique())
    max_total = agg["montant_total"].max()
    sizeref = 2.0 * max_total / (40.0**2) if max_total else 1.0

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Montant UE moyen", "Montant UE total"))
    for theme in themes:
        sub = agg[agg[theme_col] == theme]
        marker = dict(
            size=sub["montant_total"],
            sizemode="area",
            sizeref=sizeref,
            sizemin=4,
            color=(color_map or {}).get(theme),
        )
        fig.add_trace(
            go.Scatter(
                x=sub["count"],
                y=sub["montant_moyen"],
                mode="markers",
                marker=marker,
                name=theme,
                legendgroup=theme,
                showlegend=True,
                text=sub[group_col].apply(wrap_label),
                hovertemplate=(
                    f"<b>%{{text}}</b><br>{wrap_label(theme)}<br>"
                    "Nb projets : %{x}<br>Montant UE moyen : %{y:,.0f} €<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sub["count"],
                y=sub["montant_total"],
                mode="markers",
                marker=marker,
                name=theme,
                legendgroup=theme,
                showlegend=False,
                text=sub[group_col].apply(wrap_label),
                hovertemplate=(
                    f"<b>%{{text}}</b><br>{wrap_label(theme)}<br>"
                    "Nb projets : %{x}<br>Montant UE total : %{y:,.0f} €<extra></extra>"
                ),
            ),
            row=1,
            col=2,
        )

    fig.update_xaxes(title_text="Nombre de projets", row=1, col=1)
    fig.update_xaxes(title_text="Nombre de projets", row=1, col=2)
    fig.update_yaxes(title_text="Montant UE moyen (€)", row=1, col=1)
    fig.update_yaxes(title_text="Montant UE total (€)", row=1, col=2)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, title_text=theme_col),
        margin=dict(b=100),
    )
    return style_hover(fig)


def build_fonds_barchart(df_fonds, color_map, totaux_programme=None, fonds_col="fonds", amount_col="montant_ue_total", count_col="count"):
    """Barres verticales du montant engagé par fonds, colorées par fonds (color_map). Si
    totaux_programme (dict fonds -> montant programmé, Tableau 9B) est fourni, empile une
    seconde barre "Reste à engager" (programme - engagé, plancher 0) au-dessus de chaque
    barre — le sommet de la barre empilée rejoint alors l'enveloppe programmée, complémentaire
    au repère pointillé de build_cumulative_curve en mode Montant (sans objet en mode %,
    seule la courbe cumulée bascule — voir issue #33). Un fonds sans donnée programmée n'a
    simplement pas de segment "Reste à engager" (0), pas d'erreur.

    Pas de légende (showlegend=False) : avec deux barres empilées, la légende faisait perdre
    l'alignement de hauteur avec la courbe cumulée affichée à côté (même axe_range). Le détail
    engagé/reste/% consommé est reporté en tooltip sur chaque segment plutôt que par la
    légende."""
    reste = pd.Series(0, index=df_fonds.index)
    pct_consomme = pd.Series(float("nan"), index=df_fonds.index)
    if totaux_programme:
        programme = df_fonds[fonds_col].map(totaux_programme).fillna(0)
        reste = (programme - df_fonds[amount_col]).clip(lower=0)
        pct_consomme = df_fonds[amount_col] / programme.where(programme != 0)

    count_series = df_fonds[count_col] if count_col in df_fonds else pd.Series(float("nan"), index=df_fonds.index)
    customdata_engage = pd.concat([count_series, reste, pct_consomme], axis=1).values
    hover_engage = "<b>%{x}</b><br>Engagé : %{y:,.0f} €"
    if count_col in df_fonds:
        hover_engage += "<br>Nb projets : %{customdata[0]:,.0f}"
    hover_engage += "<br>Reste à engager (estimé) : %{customdata[1]:,.0f} €<br>% consommé : %{customdata[2]:.0%}<extra></extra>"

    fig = go.Figure()
    fig.add_bar(
        x=df_fonds[fonds_col],
        y=df_fonds[amount_col],
        name="Engagé",
        marker_color=[color_map.get(f, "gray") for f in df_fonds[fonds_col]],
        customdata=customdata_engage,
        hovertemplate=hover_engage,
    )
    if totaux_programme and reste.sum() > 0:
        customdata_reste = pd.concat([df_fonds[amount_col], pct_consomme], axis=1).values
        fig.add_bar(
            x=df_fonds[fonds_col],
            y=reste,
            name="Reste à engager",
            marker_color="rgba(150,150,150,0.35)",
            customdata=customdata_reste,
            hovertemplate=(
                "<b>%{x}</b><br>Reste à engager (estimé) : %{y:,.0f} €<br>Engagé : "
                "%{customdata[0]:,.0f} €<br>% consommé : %{customdata[1]:.0%}<extra></extra>"
            ),
        )
    # margin.t=60 explicite : sans ça, ce go.Figure hérite d'une marge haute par défaut différente
    # de celle de build_cumulative_curve (px.line, qui fixe systématiquement margin.t=60) — un axe Y
    # identique en valeur ne suffit donc pas à aligner visuellement les deux figures placées côte à
    # côte, leur zone de tracé démarrant à des hauteurs différentes (issue #35).
    fig.update_layout(barmode="stack", xaxis_title=None, yaxis_title="Montant UE (€)", showlegend=False, margin=dict(t=60))
    fig.update_traces(width=0.3, selector=dict(type="bar"))
    return style_hover(fig)


def build_cumulative_curve(
    df, date_col="Date de début de l'opération", amount_col="Montant UE", color_col="Fonds", color_map=None, totaux_ref=None, mode="montant"
):
    """Courbe d'engagement UE cumulé dans le temps, par color_col, avec repères verticaux à
    chaque 1ᵉʳ janvier pour situer les années. color_map (optionnel) fixe la couleur par
    catégorie plutôt que la palette par défaut. totaux_ref (optionnel, dict catégorie ->
    montant) ajoute par catégorie un repère horizontal pointillé léger au niveau de son
    montant **programmé** (Tableau 9B) — l'écart entre la courbe et ce repère est le reste à
    consommer, aligné avec le barchart "Répartition par fonds" affiché à côté (mêmes couleurs).

    mode="pourcentage" (issue #33) : trace le % de l'enveloppe programmée plutôt que le
    montant cumulé — nécessite totaux_ref (categorie -> montant programmé), les catégories
    absentes de totaux_ref sont exclues (rien à quoi rapporter un %). Retombe sur mode
    "montant" si totaux_ref est vide/absent en mode "pourcentage" (rien à diviser)."""
    plot_df = df[[date_col, amount_col, color_col]].copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col])
    plot_df = (
        plot_df.groupby([color_col, date_col], as_index=False)[amount_col]
        .sum()
        .sort_values([color_col, date_col])
    )
    plot_df["cumule"] = plot_df.groupby(color_col)[amount_col].cumsum()

    if mode == "pourcentage" and not totaux_ref:
        mode = "montant"

    if mode == "pourcentage":
        plot_df = plot_df[plot_df[color_col].isin(totaux_ref)].copy()
        plot_df["valeur"] = plot_df.apply(lambda r: r["cumule"] / totaux_ref[r[color_col]], axis=1)
        y_label = "% de l'enveloppe programmée"
    else:
        plot_df["valeur"] = plot_df["cumule"]
        y_label = "Montant UE cumulé (€)"

    fig = px.line(
        plot_df,
        x=date_col,
        y="valeur",
        color=color_col,
        color_discrete_map=color_map,
        labels={date_col: "Date", "valeur": y_label},
    )
    fig.update_traces(line=dict(width=2))
    if mode == "pourcentage":
        fig.update_yaxes(tickformat=".0%")
        fig.for_each_trace(
            lambda t: t.update(hovertemplate=f"<b>{t.name}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:.1%}} de l'enveloppe programmée<extra></extra>")
        )
    else:
        fig.for_each_trace(
            lambda t: t.update(
                hovertemplate=f"<b>{t.name}</b><br>%{{x|%d/%m/%Y}}<br>Montant UE cumulé : %{{y:,.0f}} €<extra></extra>"
            )
        )
    for year in range(plot_df[date_col].dt.year.min(), plot_df[date_col].dt.year.max() + 1):
        fig.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)
    if mode == "pourcentage":
        fig.add_hline(y=1, line_dash="dot", line_color="black", opacity=0.4)
    elif totaux_ref:
        for categorie, total in totaux_ref.items():
            couleur = (color_map or {}).get(categorie, "gray")
            fig.add_hline(y=total, line_dash="dot", line_color=couleur, opacity=0.4)
    return style_hover(fig)


def compute_cofinancement_table(df, group_col, taux_col="Taux de cofinancement"):
    """Taux de cofinancement moyen/médian par groupe, à comparer aux plafonds réglementaires
    (variables selon fonds et catégorie de région) pour repérer les écarts."""
    agg = df.groupby(group_col)[taux_col].agg(taux_moyen="mean", taux_median="median", count="count").reset_index()
    return agg.sort_values("taux_moyen", ascending=False)


def build_cofinancement_categorie_chart(df, label_col="Catégorie", ue_col="montant_ue", total_col="total_depenses", plafond_col="plafond", height=None):
    """Bullet chart : barre de fond = total des dépenses éligibles, barre superposée = montant
    financé par l'UE, par catégorie de région (utils/cofinancement.bucket_categorie) — l'écart
    visuel entre les deux extrémités de barre est le montant financé par ailleurs (national,
    local, privé). Un repère en losange marque le plafond réglementaire de cofinancement UE de
    la catégorie (utils/cofinancement.plafond_categorie), positionné à plafond * total des
    dépenses éligibles : plus la barre UE s'en approche, plus la catégorie consomme sa marge
    de cofinancement maximale autorisée."""
    df = df.sort_values(total_col)
    taux = df[ue_col] / df[total_col]
    fig = go.Figure()
    fig.add_bar(
        x=df[total_col],
        y=df[label_col],
        orientation="h",
        name="Total des dépenses éligibles",
        marker_color="#c8d4e3",
        hovertemplate="<b>%{y}</b><br>Total dépenses éligibles : %{x:,.0f} €<extra></extra>",
    )
    fig.add_bar(
        x=df[ue_col],
        y=df[label_col],
        orientation="h",
        name="Financé par l'UE",
        marker_color="#4C78A8",
        customdata=taux,
        text=[f"{t:.0%}" for t in taux],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Financé par l'UE : %{x:,.0f} €<br>Taux : %{customdata:.0%}<extra></extra>",
    )
    fig.add_scatter(
        x=df[plafond_col] * df[total_col],
        y=df[label_col],
        mode="markers",
        marker=dict(symbol="diamond", size=12, color="#e34948"),
        name="Plafond réglementaire",
        customdata=df[plafond_col],
        hovertemplate="<b>%{y}</b><br>Plafond réglementaire : %{customdata:.0%} du total des dépenses éligibles<extra></extra>",
    )
    fig.update_layout(
        barmode="overlay",
        height=height if height else max(350, 45 * len(df)),
        xaxis_title="Montant (€)",
        yaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return style_hover(fig)


def detect_cofinancement_outliers(df, taux_col="Taux de cofinancement"):
    """Opérations dont le taux de cofinancement sort de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
    (à ne pas confondre avec un dépassement de plafond réglementaire, non modélisé ici)."""
    q1, q3 = df[taux_col].quantile(0.25), df[taux_col].quantile(0.75)
    iqr = q3 - q1
    borne_basse, borne_haute = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return df[(df[taux_col] < borne_basse) | (df[taux_col] > borne_haute)].sort_values(taux_col, ascending=False)


def detect_cofinancement_superieur_plafond(df, plafond, taux_col="Taux de cofinancement"):
    """Opérations dont le taux de cofinancement UE dépasse le plafond réglementaire de la
    catégorie de région (voir utils/cofinancement.plafond_categorie) — à ne pas confondre
    avec detect_cofinancement_outliers (taux statistiquement atypique par rapport aux autres
    opérations du même fonds) : ici la référence est le taux maximal légal, pas une médiane,
    donc un signal plus directement actionnable. plafond est un taux (0-1), pas un %."""
    return df[df[taux_col] > plafond].sort_values(taux_col, ascending=False)


def detect_incoherent_cofinancement(df, amount_col="Montant UE", depenses_col="Total des dépenses éligibles"):
    """Opérations où le montant UE dépasse le total des dépenses éligibles (taux de
    cofinancement > 100%), normalement impossible — contrôle de cohérence sur les montants
    déclarés, à vérifier plutôt qu'une question de distribution statistique."""
    return df[df[amount_col] > df[depenses_col]].sort_values(amount_col, ascending=False)


def compute_top_beneficiaires(df, group_col="Nom du bénéficiaire", amount_col="Montant UE", top_n=20):
    """Bénéficiaires cumulant le plus de montant UE, tous projets confondus dans le
    périmètre affiché — repère de concentration/dépendance à quelques acteurs récurrents,
    complémentaire à la concentration par opération (compute_stats_table)."""
    agg = df.groupby(group_col)[amount_col].agg(montant_ue_total="sum", count="count").reset_index()
    return agg.sort_values("montant_ue_total", ascending=False).head(top_n)


def render_top_beneficiaires_drilldown(df, montant_col_config, key, group_col="Nom du bénéficiaire", amount_col="Montant UE", top_n=20):
    """Affiche le tableau "Top bénéficiaires" (compute_top_beneficiaires, lecture seule) puis
    un st.selectbox pour choisir un bénéficiaire et afficher le détail de tous ses projets dans
    le périmètre passé en df — issue #22 (drill-down bénéficiaire, jusqu'ici seulement agrégé
    sans vue détaillée par bénéficiaire).

    Un selectbox plutôt qu'une sélection de ligne sur le tableau (st.dataframe
    on_select/selection_mode) : Streamlit affiche une case à cocher pour la sélection de ligne
    même en selection_mode="single-row", ce qui laisse penser à tort qu'un choix multiple est
    possible — un widget dédié à choix unique est plus conforme à la convention (case à cocher
    = sélection multiple).

    key doit être unique par appel (Accueil vs Vue Régionale vs Volet National) pour que
    Streamlit ne mélange pas les sélections entre les tableaux."""
    top = compute_top_beneficiaires(df, group_col=group_col, amount_col=amount_col, top_n=top_n).rename(
        columns={"montant_ue_total": "Montant UE cumulé", "count": "Nb projets"}
    )
    st.dataframe(
        top,
        hide_index=True,
        use_container_width=True,
        column_config={**text_widths(group_col), "Montant UE cumulé": montant_col_config},
    )

    beneficiaire = st.selectbox(
        "Voir le détail des projets d'un bénéficiaire",
        options=["(choisir un bénéficiaire)"] + top[group_col].tolist(),
        key=key,
    )
    if beneficiaire == "(choisir un bénéficiaire)":
        return

    detail_cols = [
        c
        for c in ["Numéro Opération", "Intitulé du projet", "Libellé Programme", "Fonds", "Région de l'opération", amount_col, "Date de début de l'opération"]
        if c in df.columns
    ]
    detail = df[df[group_col] == beneficiaire][detail_cols].sort_values(amount_col, ascending=False)
    st.markdown(f"**Détail des projets de {beneficiaire}** ({len(detail)} opération(s))")
    st.dataframe(
        detail,
        hide_index=True,
        use_container_width=True,
        column_config={
            **text_widths("Numéro Opération", "Intitulé du projet", "Libellé Programme", "Région de l'opération"),
            amount_col: montant_col_config,
        },
    )


def build_pareto_beneficiaires(df, group_col="Nom du bénéficiaire", amount_col="Montant UE", top_n=15):
    """Diagramme de Pareto : barres des top_n bénéficiaires par montant UE, avec une courbe de
    % cumulé (calculé sur l'ensemble des bénéficiaires du périmètre, pas seulement le top
    affiché) en axe secondaire — répond à "combien de bénéficiaires portent quelle part du
    total", plus immédiatement lisible que la courbe de Lorenz pour un public non technique."""
    agg = df.groupby(group_col)[amount_col].sum().sort_values(ascending=False).reset_index()
    agg.columns = [group_col, "montant_ue_total"]
    total = agg["montant_ue_total"].sum()
    agg["cumule_pct"] = agg["montant_ue_total"].cumsum() / total
    top = agg.head(top_n)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(
        x=top[group_col],
        y=top["montant_ue_total"],
        name="Montant UE",
        hovertemplate="<b>%{x}</b><br>Montant UE : %{y:,.0f} €<extra></extra>",
    )
    fig.add_scatter(
        x=top[group_col],
        y=top["cumule_pct"],
        name="% cumulé du montant total",
        mode="lines+markers",
        line=dict(width=2),
        secondary_y=True,
        hovertemplate="<b>%{x}</b><br>% cumulé du montant total : %{y:.1%}<extra></extra>",
    )
    fig.update_yaxes(title_text="Montant UE (€)", secondary_y=False)
    fig.update_yaxes(title_text="% cumulé du montant total", tickformat=".0%", range=[0, 1], secondary_y=True)
    fig.update_xaxes(tickangle=-30)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_hover(fig)


def build_lorenz_beneficiaires(df, group_col="Nom du bénéficiaire", amount_col="Montant UE"):
    """Courbe de Lorenz : % cumulé de bénéficiaires (triés du plus petit au plus grand montant)
    vs % cumulé du montant UE, avec la diagonale d'égalité parfaite en référence — plus la
    courbe s'écarte de la diagonale, plus le montant est concentré sur peu de bénéficiaires.
    Cohérent avec le coefficient concentration_top10 déjà calculé dans compute_stats_table."""
    agg = df.groupby(group_col)[amount_col].sum().sort_values(ascending=True).reset_index()
    n = len(agg)
    total = agg[amount_col].sum()
    agg["cumule_pct_montant"] = agg[amount_col].cumsum() / total
    agg["cumule_pct_beneficiaires"] = pd.RangeIndex(1, n + 1) / n

    x = [0] + agg["cumule_pct_beneficiaires"].tolist()
    y = [0] + agg["cumule_pct_montant"].tolist()

    fig = go.Figure()
    fig.add_scatter(
        x=x,
        y=y,
        mode="lines",
        name="Courbe de Lorenz",
        line=dict(width=2),
        hovertemplate="%{x:.0%} des bénéficiaires portent %{y:.0%} du montant<extra></extra>",
    )
    fig.add_scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Égalité parfaite", line=dict(width=1, dash="dot", color="gray"), hoverinfo="skip"
    )
    fig.update_xaxes(title_text="% cumulé des bénéficiaires", tickformat=".0%", range=[0, 1])
    fig.update_yaxes(title_text="% cumulé du montant UE", tickformat=".0%", range=[0, 1])
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
    return style_hover(fig)


def _cluster_operations_proches(df, beneficiaire_col, amount_col, date_col, max_days, max_relative_diff):
    """Pour chaque bénéficiaire ayant au moins 2 opérations, identifie celles dont le montant
    (écart relatif ≤ max_relative_diff) et la date de début (écart ≤ max_days) sont proches d'au
    moins une autre opération du même bénéficiaire. Retourne une liste de (bénéficiaire,
    sous-DataFrame des opérations concernées) — brique commune aux deux tables construites par
    detect_regroupements_beneficiaire, qui n'en diffèrent que par la taille du regroupement
    retenue."""
    work = df[[beneficiaire_col, "Numéro Opération", "Intitulé du projet", "Libellé Programme", "Fonds", date_col, amount_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col])

    clusters = []
    for beneficiaire, group in work.groupby(beneficiaire_col):
        if len(group) < 2:
            continue
        records = group.to_dict("records")
        involved_numeros = set()
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i], records[j]
                m1, m2 = a[amount_col], b[amount_col]
                if not isinstance(m1, (int, float)) or not isinstance(m2, (int, float)) or math.isnan(m1) or math.isnan(m2) or m1 == 0 or m2 == 0:
                    continue
                if abs((a[date_col] - b[date_col]).days) > max_days:
                    continue
                if abs(m1 - m2) / max(m1, m2) > max_relative_diff:
                    continue
                involved_numeros.add(a["Numéro Opération"])
                involved_numeros.add(b["Numéro Opération"])

        if len(involved_numeros) >= 2:
            clusters.append((beneficiaire, group[group["Numéro Opération"].isin(involved_numeros)]))

    return clusters


def detect_regroupements_beneficiaire(
    df,
    beneficiaire_col="Nom du bénéficiaire",
    amount_col="Montant UE",
    date_col="Date de début de l'opération",
    max_days=60,
    max_relative_diff=0.15,
    max_group_size=3,
):
    """Pour chaque bénéficiaire, regroupe ses opérations dont le montant et la date de début sont
    proches d'au moins une autre opération du même bénéficiaire. Retourne trois tables à partir
    du même calcul (évite de le refaire plusieurs fois, coûteux sur tout le périmètre national) :

    - petits_regroupements : bénéficiaires avec ≤ max_group_size opérations rapprochées (nombre
      d'opérations, montant cumulé)
    - grands_regroupements : au-delà de max_group_size (typiquement des programmes découpés en
      plusieurs lots), avec en plus le coefficient de variation des montants au sein du
      regroupement — une dispersion élevée indique des lots de taille très inégale, une
      dispersion quasi nulle indique des lots de montant quasi identique.
    - inter_fonds : sous-ensemble des regroupements ci-dessus (petits et grands confondus) dont
      les opérations couvrent plus d'un Fonds (FEDER/FSE+/FTJ) pour ce bénéficiaire — signal plus
      fort qu'un simple regroupement intra-programme (accord-cadre en plusieurs lots, même Fonds,
      qui reste la lecture la plus fréquente d'un grand regroupement). Table dédiée plutôt qu'un
      indicateur noyé dans les deux tables ci-dessus : le volume de cas inter-fonds est faible
      (dizaines, pas centaines) et mérite sa propre vue plutôt qu'un tri en tête de liste."""
    clusters = _cluster_operations_proches(df, beneficiaire_col, amount_col, date_col, max_days, max_relative_diff)

    petits_rows, grands_rows, inter_fonds_rows = [], [], []
    for beneficiaire, involved in clusters:
        montants = involved[amount_col]
        fonds = sorted(set(involved["Fonds"]))
        row = {
            beneficiaire_col: beneficiaire,
            "Nb opérations rapprochées": len(involved),
            "Montant UE cumulé": montants.sum(),
            "Première date": involved[date_col].min(),
            "Dernière date": involved[date_col].max(),
        }
        if len(involved) <= max_group_size:
            petits_rows.append(
                {
                    **row,
                    "Opérations": "; ".join(involved["Intitulé du projet"]),
                    "Programme(s)": "; ".join(sorted(set(involved["Libellé Programme"]))),
                }
            )
        else:
            moyenne = montants.mean()
            grands_rows.append({**row, "Coeff. de variation": (montants.std() / moyenne) if moyenne else 0})

        if len(fonds) > 1:
            inter_fonds_rows.append(
                {
                    **row,
                    "Fonds": "; ".join(fonds),
                    "Programme(s)": "; ".join(sorted(set(involved["Libellé Programme"]))),
                    "Opérations": "; ".join(involved["Intitulé du projet"]),
                }
            )

    common_cols = [beneficiaire_col, "Nb opérations rapprochées", "Montant UE cumulé", "Première date", "Dernière date"]
    petits_cols = common_cols + ["Opérations", "Programme(s)"]
    grands_cols = common_cols[:3] + ["Coeff. de variation"] + common_cols[3:]
    inter_fonds_cols = common_cols[:3] + ["Fonds", "Programme(s)", "Opérations"] + common_cols[3:]

    petits = pd.DataFrame(petits_rows, columns=petits_cols) if petits_rows else pd.DataFrame(columns=petits_cols)
    grands = pd.DataFrame(grands_rows, columns=grands_cols) if grands_rows else pd.DataFrame(columns=grands_cols)
    inter_fonds = (
        pd.DataFrame(inter_fonds_rows, columns=inter_fonds_cols)
        if inter_fonds_rows
        else pd.DataFrame(columns=inter_fonds_cols)
    )
    return (
        petits.sort_values("Montant UE cumulé", ascending=False),
        grands.sort_values("Montant UE cumulé", ascending=False),
        inter_fonds.sort_values("Montant UE cumulé", ascending=False),
    )


def detect_beneficiaires_multi_region(
    df,
    fuzzy_clusters,
    beneficiaire_col="Nom du bénéficiaire",
    region_col="regions_modernes",
    amount_col="Montant UE",
):
    """Repère les bénéficiaires (ou variantes de saisie rapprochées via fuzzy_clusters, voir
    data-pipeline/beneficiaire_matching.py et issue #23) présents dans plusieurs régions à la
    fois — signal à recouper pour un éventuel double financement, indépendamment de la
    proximité montant/date (contrairement à detect_regroupements_beneficiaire, qui vise les
    doublons proches dans le temps).

    La clé de regroupement est le cluster fuzzy si le nom en fait partie, sinon le nom exact
    tel quel — donc les doublons exacts entre régions (même nom saisi à l'identique) sont
    aussi couverts, pas seulement les variantes approchées."""
    work = df[[beneficiaire_col, region_col, "Fonds", "Numéro Opération", amount_col]].copy()
    work["_cle"] = work[beneficiaire_col].map(lambda n: fuzzy_clusters.get(n, n))

    rows = []
    for cle, group in work.groupby("_cle"):
        regions = set()
        for r in group[region_col]:
            regions.update(r or [])
        if len(regions) < 2:
            continue
        noms = sorted(set(group[beneficiaire_col]))
        rows.append(
            {
                beneficiaire_col: " / ".join(noms),
                "Rapprochement": "approché (variantes de saisie)" if len(noms) > 1 else "exact",
                "Régions": ", ".join(sorted(regions)),
                "Fonds": ", ".join(sorted(set(group["Fonds"]))),
                "Nb opérations": len(group),
                "Montant UE cumulé": group[amount_col].sum(),
            }
        )

    cols = [beneficiaire_col, "Rapprochement", "Régions", "Fonds", "Nb opérations", "Montant UE cumulé"]
    result = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    return result.sort_values("Montant UE cumulé", ascending=False)
