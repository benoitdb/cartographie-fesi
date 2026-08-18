import streamlit as st

# Largeur par défaut pour les colonnes de texte libre qui reviennent dans plusieurs tableaux
# du dashboard (issue #34) : sans borne, ces colonnes prennent une largeur disproportionnée à
# l'affichage et rejettent les colonnes montant hors du cadre visible ou les rendent illisibles.
TEXT_COLUMN_WIDTHS = {
    "Intitulé du projet": "large",
    "Nom du bénéficiaire": "medium",
    "Opérations": "large",
    "Programme(s)": "medium",
    "Libellé Programme": "medium",
    "Programme": "large",
    "Objectif stratégique": "large",
    "Région": "medium",
    "Régions": "medium",
    "Région de l'opération": "medium",
    "Région du département": "medium",
    "Autres régions": "medium",
    "Catégorie d'origine": "medium",
    "Rapprochement": "medium",
    "Numéro Opération": "small",
    "Département": "small",
    "Rattachement": "small",
    "Type": "small",
    "Code CCI": "small",
}


def text_widths(*column_names):
    """column_config pour des colonnes de texte libre connues (TEXT_COLUMN_WIDTHS), à
    fusionner dans le column_config d'un st.dataframe : column_config={**text_widths(...), ...}."""
    return {name: st.column_config.TextColumn(width=TEXT_COLUMN_WIDTHS[name]) for name in column_names if name in TEXT_COLUMN_WIDTHS}
