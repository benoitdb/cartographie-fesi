"""Fraîcheur des données, affichée à l'utilisateur.

Le fichier source est republié **5 fois par an** en « annule et remplace ». Le
pipeline retient déjà le millésime le plus récent et le journalise, mais rien à
l'écran ne distinguait jusqu'ici des chiffres du jour d'un export vieux de
plusieurs mois (issue #47) — un dashboard de pilotage sans date affichée invite
à conclure sur des montants dont on ignore l'âge.

La date vient de `metadata.millesime` (`data.json`), extraite du nom du fichier
source par `data-pipeline/schema_source.millesime_du_fichier`.
"""

from datetime import date

import streamlit as st


def libelle_millesime(metadata):
    """« export du 16/03/2026 », ou None si la date est absente ou illisible.

    None plutôt qu'un texte de repli : mieux vaut n'afficher aucune date que
    d'en afficher une fausse, ou un « date inconnue » qui n'apprend rien et
    occupe la place."""
    millesime = (metadata or {}).get("millesime")
    if not millesime:
        return None
    try:
        jour = date.fromisoformat(millesime)
    except (TypeError, ValueError):
        return None
    return f"export du {jour.strftime('%d/%m/%Y')}"


def render_millesime(metadata):
    """Affiche la fraîcheur des données en pied de barre latérale, donc sur
    toutes les pages sans occuper la surface d'analyse."""
    libelle = libelle_millesime(metadata)
    if libelle:
        st.sidebar.caption(f"Données : {libelle}")
