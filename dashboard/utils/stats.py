import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.plot_style import format_montant, style_hover, wrap_label


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


def build_cumulative_curve(df, date_col="Date de début de l'opération", amount_col="Montant UE", color_col="Fonds"):
    """Courbe d'engagement UE cumulé dans le temps, par color_col, avec repères verticaux à
    chaque 1ᵉʳ janvier pour situer les années."""
    plot_df = df[[date_col, amount_col, color_col]].copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col])
    plot_df = (
        plot_df.groupby([color_col, date_col], as_index=False)[amount_col]
        .sum()
        .sort_values([color_col, date_col])
    )
    plot_df["cumule"] = plot_df.groupby(color_col)[amount_col].cumsum()

    fig = px.line(
        plot_df,
        x=date_col,
        y="cumule",
        color=color_col,
        labels={date_col: "Date", "cumule": "Montant UE cumulé (€)"},
    )
    fig.update_traces(line=dict(width=2))
    fig.for_each_trace(
        lambda t: t.update(
            hovertemplate=f"<b>{t.name}</b><br>%{{x|%d/%m/%Y}}<br>Montant UE cumulé : %{{y:,.0f}} €<extra></extra>"
        )
    )
    for year in range(plot_df[date_col].dt.year.min(), plot_df[date_col].dt.year.max() + 1):
        fig.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)
    return style_hover(fig)


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


def _cluster_operations_proches(df, beneficiaire_col, amount_col, date_col, max_days, max_relative_diff):
    """Pour chaque bénéficiaire ayant au moins 2 opérations, identifie celles dont le montant
    (écart relatif ≤ max_relative_diff) et la date de début (écart ≤ max_days) sont proches d'au
    moins une autre opération du même bénéficiaire. Retourne une liste de (bénéficiaire,
    sous-DataFrame des opérations concernées) — brique commune aux deux tables construites par
    detect_regroupements_beneficiaire, qui n'en diffèrent que par la taille du regroupement
    retenue."""
    work = df[[beneficiaire_col, "Numéro Opération", "Intitulé du projet", "Libellé Programme", date_col, amount_col]].copy()
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
                if not m1 or not m2:
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
    proches d'au moins une autre opération du même bénéficiaire. Retourne deux tables à partir du
    même calcul (évite de le refaire deux fois, coûteux sur tout le périmètre national) :

    - petits_regroupements : bénéficiaires avec ≤ max_group_size opérations rapprochées (nombre
      d'opérations, montant cumulé)
    - grands_regroupements : au-delà de max_group_size (typiquement des programmes découpés en
      plusieurs lots), avec en plus le coefficient de variation des montants au sein du
      regroupement — une dispersion élevée indique des lots de taille très inégale, une
      dispersion quasi nulle indique des lots de montant quasi identique."""
    clusters = _cluster_operations_proches(df, beneficiaire_col, amount_col, date_col, max_days, max_relative_diff)

    petits_rows, grands_rows = [], []
    for beneficiaire, involved in clusters:
        montants = involved[amount_col]
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

    common_cols = [beneficiaire_col, "Nb opérations rapprochées", "Montant UE cumulé", "Première date", "Dernière date"]
    petits_cols = common_cols + ["Opérations", "Programme(s)"]
    grands_cols = common_cols[:3] + ["Coeff. de variation"] + common_cols[3:]

    petits = pd.DataFrame(petits_rows, columns=petits_cols) if petits_rows else pd.DataFrame(columns=petits_cols)
    grands = pd.DataFrame(grands_rows, columns=grands_cols) if grands_rows else pd.DataFrame(columns=grands_cols)
    return (
        petits.sort_values("Montant UE cumulé", ascending=False),
        grands.sort_values("Montant UE cumulé", ascending=False),
    )
