import pandas as pd
import streamlit as st

FONDS_OPTIONS = ["FEDER", "FSE+", "FTJ"]


def render_fonds_filter():
    """Widget sidebar Fonds, partagé entre les pages via une key commune (state préservé
    lors de la navigation multipage Streamlit)."""
    with st.sidebar:
        st.header("Filtres")
        selected = st.multiselect("Fonds", FONDS_OPTIONS, default=FONDS_OPTIONS, key="filtre_fonds")
    if not selected:
        st.warning("Sélectionnez au moins un fonds dans la barre latérale.")
        st.stop()
    return selected


def summarize_ops(ops):
    """Résumé montant/count/moyenne à partir d'une liste d'opérations brutes."""
    df = pd.DataFrame(ops)
    if df.empty:
        return {"montant_ue_total": 0, "count": 0, "montant_ue_moyen": 0}
    montant_total = df["Montant UE"].sum()
    count = len(df)
    return {
        "montant_ue_total": montant_total,
        "count": count,
        "montant_ue_moyen": montant_total / count if count else 0,
    }


def compute_by_region(ops):
    """Équivalent de aggregates.by_region, recalculé depuis des opérations brutes
    (mono-région, hors interrégional/national) — utilisé quand un filtre fonds est actif."""
    df = pd.DataFrame(ops)
    if df.empty:
        return {}
    mono_region = df["regions_modernes"].apply(lambda r: isinstance(r, list) and len(r) == 1)
    df = df[mono_region & ~df["is_interregional"] & ~df["is_national"]].copy()
    df["region"] = df["regions_modernes"].apply(lambda r: r[0])
    agg = df.groupby("region").agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
    return agg.to_dict("index")
