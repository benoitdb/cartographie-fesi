import re

# Taux de cofinancement UE maximal par catégorie de région (politique de cohésion 2021-2027,
# règlement (UE) 2021/1060, art. 112) : 85% moins développée, 60% en transition, 50% plus
# développée. Les régions ultrapériphériques (RUP, art. 349 TFUE) bénéficient du plafond le
# plus élevé (85%) quelle que soit leur catégorie de base — voir cohesion_ue.py.
#
# Ces mêmes seuils numériques (85/60/50) valent aussi pour 2014-2020 (règlement (UE)
# n° 1303/2013, art. 120 §3) : ce n'est pas ce dictionnaire qui change d'une période à
# l'autre, mais la région → catégorie sous-jacente (2014-2020 :
# data/processed/categories_ue_2014_2020.json, issue #81).
#
# L'article 120 §3 comporte un quatrième palier, à 80%, pour les régions moins développées
# dont le PIB/hab. 2007-2009 se situait entre 75% et 85% de la moyenne UE-27 — cas
# transitoire hérité de 2007-2013. Il n'est pas transcrit ici parce qu'**aucune région
# française n'y tombe** : la France n'avait pas de région moins développée en métropole, et
# ses régions moins développées (les DROM) sont ultrapériphériques, donc à 85%. L'ajouter
# reviendrait à porter une clé qu'aucune donnée ne peut atteindre. Voir
# docs/sources/reglement_1303_2013_cofinancement_2014_2020.md.
PLAFOND_PAR_CATEGORIE = {
    "plus développée": 0.50,
    "en transition": 0.60,
    "moins développée": 0.85,
}
PLAFOND_RUP = 0.85

# Fonds 2014-2020 auxquels PLAFOND_PAR_CATEGORIE n'est **pas opposable**, quelle que soit la
# catégorie de région. Ce ne sont pas des exceptions de confort : chacune est écrite dans un
# texte, et appliquer le plafond de droit commun à ces opérations produit un faux positif
# garanti — exactement le défaut d'outil que l'issue #81 devait éviter.
#
# - `FEDER REACT-EU` : dérogation explicite à l'article 120, taux « pouvant aller jusqu'à
#   100 % » (règlement (UE) 2020/2221, art. 92 ter §12). Médiane à 100 % par construction.
# - `IEJ` : l'article 120 §3, dernier alinéa, dit que le taux maximal « **augmente** pour
#   chaque axe prioritaire mettant en œuvre l'IEJ », l'augmentation étant fixée par les
#   règles spécifiques du FSE. Le plafond de catégorie est donc un plancher pour l'IEJ, pas
#   un plafond — 138 opérations IEJ des seuls Hauts-de-France le dépassent, à 75 % de
#   médiane, sans que rien n'y soit irrégulier.
# - `FEAD` : hors champ. Les Fonds ESI de 1303/2013 sont FEDER, FSE, Fonds de cohésion,
#   FEADER et FEAMP ; le FEAD est financé par un **transfert hors** de l'enveloppe des Fonds
#   structurels (art. 94), et relève du règlement (UE) 223/2014, qui a son propre taux.
#
# Un ensemble de libellés exacts, et non un test par sous-chaîne : les libellés viennent du
# fichier Synergie, et une correspondance approximative attraperait demain un fonds dont le
# nom mentionnerait l'un de ceux-ci sans relever du même régime.
FONDS_HORS_PLAFOND = frozenset({"FEDER REACT-EU", "IEJ", "FEAD"})

# Regex pour les catégories mixtes telles que transcrites dans region_metadata.json (voir
# cohesion_ue.py _weighted_categorie_from_programmes) : "Mixte : 57% Plus développée / 43%
# En transition (FEDER)".
_MIXTE_PART_RE = re.compile(r"(\d+)%\s*([^/(]+)")


def plafond_categorie(categorie_ue, ultraperipherique=False):
    """Taux de cofinancement UE maximal applicable, ou None si la catégorie est absente/non
    reconnue. Une région ultrapériphérique a toujours 85%, indépendamment de sa catégorie de
    base. Une catégorie mixte (ex. Auvergne-Rhône-Alpes) retourne la moyenne pondérée des
    plafonds de chaque catégorie composante, au prorata des poids transcrits dans le libellé."""
    if ultraperipherique:
        return PLAFOND_RUP
    if not categorie_ue:
        return None

    categorie_lower = categorie_ue.strip().lower()
    if categorie_lower in PLAFOND_PAR_CATEGORIE:
        return PLAFOND_PAR_CATEGORIE[categorie_lower]

    poids_total, plafond_pondere = 0, 0.0
    for poids_str, label in _MIXTE_PART_RE.findall(categorie_ue):
        rate = PLAFOND_PAR_CATEGORIE.get(label.strip().lower())
        if rate is None:
            continue
        poids = int(poids_str)
        poids_total += poids
        plafond_pondere += poids * rate
    return plafond_pondere / poids_total if poids_total else None


def est_hors_plafond(fonds):
    """Vrai si ce fonds échappe aux plafonds de l'article 120 (voir FONDS_HORS_PLAFOND)."""
    return fonds in FONDS_HORS_PLAFOND


def filtrer_fonds_plafonnes(df, fonds_col="Fonds"):
    """Opérations auxquelles un plafond réglementaire est opposable — les autres en sont
    retirées, plutôt que comparées à une borne qui ne les régit pas. Retourne (df filtré,
    nombre d'opérations écartées) : l'appelant doit pouvoir dire à l'écran combien
    d'opérations sortent du décompte et pourquoi, sinon l'écart se lit comme une perte."""
    if fonds_col not in df.columns:
        return df, 0
    retenues = ~df[fonds_col].isin(FONDS_HORS_PLAFOND)
    return df[retenues], int((~retenues).sum())


def plafond_intervalle_2014_2020(infos_region):
    """Plafond(s) applicable(s) à une région moderne en 2014-2020, sous forme (min, max).

    Un intervalle et non un nombre, parce que six régions modernes sur treize réunissent des
    anciennes régions de catégories différentes (contre une seule en 2021-2027) : les
    programmes de la période sont bâtis par **ancienne** région, chacun mono-catégorie, si
    bien qu'une région mixte n'a pas *un* plafond mais deux selon l'ancienne région dont
    relève l'opération — information que le fichier d'opérations ne porte pas.

    Une moyenne pondérée serait possible en 2021-2027 (les dotations par catégorie y sont
    connues, voir plafond_categorie) ; ici elle demanderait la table des dotations de
    l'Accord de partenariat 2014-2020, non transcrite (issue #93). D'ici là, mieux vaut
    afficher la fourchette réelle qu'un nombre unique qu'aucune source ne soutient.

    Retourne None si la région est inconnue ou sans catégorie exploitable — l'appelant
    n'affiche alors pas de plafond du tout.
    """
    if not infos_region:
        return None

    categorie = infos_region.get("categorie_ue")
    if categorie:
        plafond = PLAFOND_PAR_CATEGORIE.get(categorie.strip().lower())
        return (plafond, plafond) if plafond is not None else None

    plafonds = [
        PLAFOND_PAR_CATEGORIE[categorie_ancienne.strip().lower()]
        for _, categorie_ancienne in infos_region.get("composantes", [])
        if categorie_ancienne.strip().lower() in PLAFOND_PAR_CATEGORIE
    ]
    return (min(plafonds), max(plafonds)) if plafonds else None


def libelle_categorie_2014_2020(infos_region):
    """Catégorie de la période telle qu'affichée, en nommant les anciennes régions quand
    elles divergent — « mixte » seul n'apprendrait rien et laisserait croire à une donnée
    manquante plutôt qu'à un découpage disparu."""
    if not infos_region:
        return "Non classifiée"
    if infos_region.get("categorie_ue"):
        return infos_region["categorie_ue"].capitalize()
    detail = ", ".join(f"{ancienne} : {categorie}" for ancienne, categorie in infos_region.get("composantes", []))
    return f"Mixte ({detail})" if detail else "Non classifiée"


def bucket_categorie(categorie_ue, ultraperipherique=False):
    """Regroupe une région dans un intitulé de catégorie affichable (pour agréger plusieurs
    régions ensemble, ex. graphe national par catégorie) : les 3 catégories de cohésion
    telles quelles, "+ RUP" ajouté si ultrapériphérique, "Mixte" pour les régions à cheval sur
    deux catégories (transcrites avec un libellé "Mixte : ...")."""
    if not categorie_ue:
        return "Non classifiée"
    categorie_lower = categorie_ue.strip().lower()
    if categorie_lower in PLAFOND_PAR_CATEGORIE:
        label = categorie_ue.strip().capitalize()
    elif categorie_lower.startswith("mixte"):
        label = "Mixte"
    else:
        label = categorie_ue.strip()
    return f"{label} + RUP" if ultraperipherique else label
