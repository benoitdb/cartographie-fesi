"""Validation de la source : le profil factuel d'un fichier de données.

Affiche le profil calculé par data-pipeline/profil_source.py (issue #69) :
volumétrie, complétude par champ, répartition par fonds, régions, dates,
cohérence des montants. Objectif — permettre à un gestionnaire technique en
région ou à l'autorité d'audit de vérifier qu'une source est bien celle
attendue, et connue dans ses limites, avant qu'on en tire des chiffres.

Registre volontairement descriptif : on montre ce que contient la donnée et à
quel point elle est remplie, sans la juger. La page lit le profil JSON committé,
pas le XLSX brut.
"""

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_profils_source
from utils.themes import FONDS_COLORS, style_categorical_columns

st.set_page_config(page_title="Validation de la source - Cartographie FESI", layout="wide")


def _fr_date(iso):
    """« 30/08/2023 » depuis une date ISO, ou « — » si absente/illisible."""
    if not iso:
        return "—"
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "—"


def _montant(euros):
    """Montant en Md€ au-delà du milliard, sinon en M€ — lisible sans zéros à rallonge."""
    if euros is None:
        return "—"
    if abs(euros) >= 1e9:
        return f"{euros / 1e9:.2f} Md€".replace(".", ",")
    return f"{euros / 1e6:.1f} M€".replace(".", ",")


def _nombre(valeur):
    """Séparateur de milliers en espace fine insécable, comme partout ailleurs."""
    return f"{valeur:,}".replace(",", " ")


def _pourcent(valeur):
    """« 63,1 % » — virgule décimale française, alignée sur le reste de la page."""
    if valeur is None:
        return "—"
    return f"{valeur:.1f} %".replace(".", ",")


def _boite(colonne, label, valeur):
    with colonne, st.container(border=True):
        st.markdown(f"**{label} :** {valeur}")


st.title("Validation de la source")
st.caption(
    "Profil factuel des fichiers de données avant exploitation : volumétrie, complétude, "
    "périmètre et cohérence des montants. De quoi vérifier qu'une source est bien celle "
    "attendue, et connue dans ses limites."
)

profils = load_profils_source()
if not profils:
    st.info("Aucun profil de source disponible. Le générer via `data-pipeline/profil_source.py`.")
    st.stop()


def _libelle_source(entree):
    return f"{entree.get('source_label', entree['fichier_source'])} · {entree['periode']}"


# Un rapport par source (un fichier) : le sélecteur n'apparaît qu'à partir de
# deux profils, mais la source reste identifiée même quand il n'y en a qu'une.
if len(profils) > 1:
    entree = st.selectbox("Source", profils, format_func=_libelle_source)
else:
    entree = profils[0]
    st.caption(f"Source : **{_libelle_source(entree)}**")
profil = entree["profil"]

# --- Métadonnées de la source ---
meta = st.columns(3)
_boite(meta[0], "Fichier source", entree["fichier_source"])
_boite(meta[1], "Export du", _fr_date(entree.get("date_source")))
_boite(meta[2], "Profil généré le", _fr_date(entree.get("date_generation")))

# --- Indicateurs de tête ---
vol = profil["volumetrie"]
montants = profil.get("montants", {})
cle = profil.get("cle", {})
kpi = st.columns(4)
_boite(kpi[0], "Opérations", _nombre(vol["operations"]))
_boite(kpi[1], "Montant UE total", _montant(montants.get("montant_ue_total")))
cofi = montants.get("cofinancement_global")
_boite(kpi[2], "Cofinancement global", _pourcent(cofi))
_boite(kpi[3], "Clé — doublons", f"{cle.get('doublons', 0)} (sur {_nombre(cle.get('distincts', 0))} distincts)")

# --- Complétude par champ ---
st.subheader("Complétude des champs")
st.caption(
    "Part des opérations où le champ est renseigné. Un champ peu rempli n'est pas "
    "forcément une lacune — voir plus bas la région, récupérable autrement."
)
comp = profil["completude"]
df_comp = pd.DataFrame(
    [{"Champ": v["libelle"], "Complétude": v["taux"] / 100, "Renseignés": v["remplis"]}
     for v in comp.values()]
)
st.dataframe(
    df_comp,
    hide_index=True,
    width='stretch',
    column_config={
        "Complétude": st.column_config.ProgressColumn(
            "Complétude", format="percent", min_value=0, max_value=1.0
        ),
        "Renseignés": st.column_config.NumberColumn("Renseignés", format="%d"),
    },
)

# --- Région : colonne brute vs dérivée du programme ---
if "region_derivable" in profil:
    st.subheader("Région : colonne brute vs dérivée du programme")
    rd = profil["region_derivable"]
    regions = profil.get("regions", {})
    boites = st.columns(3)
    _boite(boites[0], "Colonne « Région » renseignée", _pourcent(regions.get("taux_colonne_remplie", 0)))
    _boite(boites[1], "Région dérivable du programme", _pourcent(rd["taux_operations_resolues"]))
    _boite(boites[2], "Rattachables au total", _pourcent(rd.get("taux_operations_couvertes", 0)))
    st.caption(
        "Deux voies pour rattacher une opération à une région : la colonne « Région », et le "
        "libellé du programme quand celui-ci ne couvre qu'une région. Selon la période, c'est "
        "l'une ou l'autre qui porte l'essentiel — c'est leur réunion qui compte. "
        + _nombre(rd.get("operations_sans_region", 0))
        + f" opération(s) sur {_nombre(vol['operations'])}"
        + " ne passent par aucune des deux."
    )
    st.markdown("**Programmes sans région dérivée du libellé :**")
    st.caption(
        "Programmes nationaux et interrégionaux — qui n'ont pas de région unique par "
        "construction — mais aussi, le cas échéant, libellés qu'un mapping ne reconnaît pas. "
        "La distinction se fait à la lecture, elle n'est pas dans la donnée."
    )
    for prog in rd["programmes_sans_region_unique"]:
        st.markdown(f"- {prog}")

# --- Répartition par fonds ---
st.subheader("Répartition par fonds")
df_fonds = pd.DataFrame([
    {"Fonds": f["fonds"], "Opérations": f["nb"], "Montant UE": f["montant_ue"],
     "Part du montant": f["part_montant"] / 100}
    for f in profil["par_fonds"]
])
col_table, col_graph = st.columns([5, 4])
with col_table:
    st.dataframe(
        style_categorical_columns(df_fonds, {"Fonds": FONDS_COLORS}),
        hide_index=True,
        width='stretch',
        column_config={
            "Montant UE": st.column_config.NumberColumn("Montant UE", format="%.0f €"),
            "Part du montant": st.column_config.ProgressColumn(
                "Part du montant", format="percent", min_value=0, max_value=1.0
            ),
        },
    )
with col_graph:
    fig = px.bar(
        df_fonds, x="Montant UE", y="Fonds", orientation="h", color="Fonds",
        color_discrete_map=FONDS_COLORS,
    )
    fig.update_layout(showlegend=False, height=320, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_yaxes(categoryorder="total ascending", title=None)
    fig.update_xaxes(title="Montant UE (€)")
    st.plotly_chart(fig, width='stretch')

# --- Dimension thématique ---
if "dimension_thematique" in profil:
    dim = profil["dimension_thematique"]
    st.subheader("Dimension thématique")
    if dim["taux_remplie"] == 0:
        st.info(
            f"Le champ « {dim['libelle']} » est vide sur l'ensemble du fichier : cette source "
            "ne porte pas de dimension thématique exploitable en l'état."
        )
    else:
        st.caption(f"« {dim['libelle']} » renseigné à {_pourcent(dim['taux_remplie'])} · "
                   f"{dim['distincts']} valeurs distinctes.")
        st.dataframe(
            pd.DataFrame(dim["top"]).rename(columns={"valeur": dim["libelle"], "nb": "Opérations"}),
            hide_index=True, width='stretch',
        )

# --- Dates de programmation ---
if "dates" in profil and profil["dates"]["par_annee"]:
    st.subheader("Répartition par année")
    dates = profil["dates"]
    # La date de référence diffère selon la période (programmation en 2014-2020,
    # première convention en 2021-2027) : on affiche laquelle plutôt que de
    # laisser croire à un champ unique. `libelle` absent des profils générés
    # avant son ajout — on retombe sur un intitulé neutre.
    st.caption(f"Sur « {dates.get('libelle', 'date de référence')} ».")
    df_annees = pd.DataFrame(
        [{"Année": annee, "Opérations": nb} for annee, nb in dates["par_annee"].items()]
    )
    fig_annees = px.bar(df_annees, x="Année", y="Opérations")
    fig_annees.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_annees, width='stretch')
    if dates["illisibles"]:
        st.caption(f"{dates['illisibles']} date(s) illisible(s), exclues de la répartition.")
