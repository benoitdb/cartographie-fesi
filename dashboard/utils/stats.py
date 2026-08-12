import math

import pandas as pd
import plotly.express as px


def _concentration_top10(montants):
    """Part du montant total portée par les 10% de projets les plus importants du groupe
    (indicateur classique d'audit de dépense publique pour évaluer la dépendance à quelques
    gros projets vs. une répartition diffuse)."""
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


def detect_outliers(df, amount_col="Montant UE"):
    """Opérations dont le montant sort de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]."""
    q1, q3 = df[amount_col].quantile(0.25), df[amount_col].quantile(0.75)
    iqr = q3 - q1
    borne_basse, borne_haute = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return df[(df[amount_col] < borne_basse) | (df[amount_col] > borne_haute)].sort_values(
        amount_col, ascending=False
    )


def build_histogram(df, amount_col="Montant UE", nbins=50, log_x=False, color_col=None):
    """Histogramme des montants, empilé par color_col si fourni. En échelle logarithmique
    (recommandé pour ces données, fortement asymétriques : une majorité de petites opérations
    et une minorité de très gros projets), les bins sont calculés en espace log pour rester
    réguliers à l'affichage."""
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
    return fig


def build_boxplot(df, group_col, amount_col="Montant UE", log_y=False):
    """Box plot (médiane, quartiles/IQR, outliers) des montants par groupe — visualisation
    directe de ce que présente compute_stats_table. Échelle log recommandée vu l'asymétrie
    des montants (sinon les boîtes des groupes à petits montants sont écrasées par les outliers)."""
    fig = px.box(
        df,
        x=group_col,
        y=amount_col,
        color=group_col,
        points="outliers",
        labels={amount_col: "Montant UE (€)"},
    )
    fig.update_layout(showlegend=False)
    if log_y:
        fig.update_yaxes(type="log")
    return fig


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
    return fig


def compute_cofinancement_table(df, group_col, taux_col="Taux de cofinancement"):
    """Taux de cofinancement moyen/médian par groupe, à comparer aux plafonds réglementaires
    (variables selon fonds et catégorie de région) pour repérer les écarts."""
    agg = df.groupby(group_col)[taux_col].agg(taux_moyen="mean", taux_median="median", count="count").reset_index()
    return agg.sort_values("taux_moyen", ascending=False)


def detect_cofinancement_outliers(df, taux_col="Taux de cofinancement"):
    """Opérations dont le taux de cofinancement sort de [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
    (à ne pas confondre avec un dépassement de plafond réglementaire, non modélisé ici)."""
    q1, q3 = df[taux_col].quantile(0.25), df[taux_col].quantile(0.75)
    iqr = q3 - q1
    borne_basse, borne_haute = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return df[(df[taux_col] < borne_basse) | (df[taux_col] > borne_haute)].sort_values(taux_col, ascending=False)
