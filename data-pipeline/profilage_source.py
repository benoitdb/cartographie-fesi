"""Profil d'une source d'opérations, indépendant de son ingestion.

`profiler_source` calcule, à partir du DataFrame brut d'un fichier source et d'un
mapping de colonnes sémantiques, un profil structuré et sérialisable en JSON :
volumétrie, complétude par champ, répartition par fonds, régions, programmes,
dates, montants, unicité de la clé. Ce profil sert à *valider* une source avant
de l'exploiter — il est recalculable à chaque millésime et affiché tel quel par
le dashboard (page « Validation de la source »), sans que celui-ci ait besoin du
XLSX brut (issue #69).

Le registre `type: reference` du projet vaut aussi ici : le profil est une photo
factuelle et descriptive de la donnée (combien, quelle complétude, quel
périmètre), pas un jugement.

La fonction est **pure** et **agnostique de la période** : elle ne connaît pas
les libellés réels des colonnes, seulement des clés sémantiques (`fonds`,
`montant_ue`, …) que l'appelant mappe vers les libellés de sa période. Une clé
absente du mapping fait simplement disparaître la section correspondante du
profil, plutôt que d'échouer — les périodes n'ont pas toutes les mêmes champs
(2014-2020 n'a pas d'objectif stratégique ; son `Domaine d'intervention` peut
être vide à 100 %).
"""

import pandas as pd

# Clés sémantiques dont on mesure la complétude quand elles sont mappées. L'ordre
# est celui d'affichage.
_CHAMPS_COMPLETUDE = [
    "numero_operation",
    "programme",
    "beneficiaire",
    "fonds",
    "region",
    "departement",
    "dimension_thematique",
    "date_programmation",
    "montant_ue",
    "depenses",
]


def _taux(rempli, total):
    return round(100 * rempli / total, 1) if total else 0.0


def profiler_source(df, cols, deriver_region=None):
    """Profil structuré de `df`, DataFrame brut d'un fichier source.

    `cols` : mapping {clé sémantique: libellé réel de la colonne}. Les clés
    reconnues sont celles de `_CHAMPS_COMPLETUDE`, plus `pays` et `zone`. Toute
    clé absente désactive la section qui en dépend.

    `deriver_region` : callable optionnel `libellé de programme -> région ou
    None`. Fourni, il permet de mesurer la part d'opérations dont la région est
    *récupérable* depuis le programme — l'indicateur qui compte quand la colonne
    région elle-même est peu remplie (cas 2014-2020, issue #12). Absent, la
    section `region_derivable` n'est pas produite.
    """
    n = len(df)
    profil = {
        "volumetrie": {"operations": n, "colonnes": int(df.shape[1])},
        "completude": _completude(df, cols, n),
        "par_fonds": _par_fonds(df, cols, n),
    }

    if "programme" in cols:
        profil["programmes"] = _programmes(df, cols)
    if "region" in cols:
        profil["regions"] = _regions(df, cols, n)
    if deriver_region is not None and "programme" in cols:
        profil["region_derivable"] = _region_derivable(df, cols, deriver_region)
    if "dimension_thematique" in cols:
        profil["dimension_thematique"] = _dimension_thematique(df, cols, n)
    if "date_programmation" in cols:
        profil["dates"] = _dates(df, cols)
    if "montant_ue" in cols and "depenses" in cols:
        profil["montants"] = _montants(df, cols)
    if "numero_operation" in cols:
        profil["cle"] = _cle(df, cols)
    if "pays" in cols:
        profil["pays"] = _valeurs_top(df, cols["pays"], 10)

    return profil


def _completude(df, cols, n):
    """Taux de remplissage des champs mappés, dans l'ordre de `_CHAMPS_COMPLETUDE`."""
    out = {}
    for cle in _CHAMPS_COMPLETUDE:
        if cle not in cols:
            continue
        libelle = cols[cle]
        remplis = int(df[libelle].notna().sum())
        out[cle] = {
            "libelle": libelle,
            "remplis": remplis,
            "manquants": n - remplis,
            "taux": _taux(remplis, n),
        }
    return out


def _par_fonds(df, cols, n):
    """Nombre et montant UE par fonds, trié par montant décroissant. Les parts
    permettent à la page de situer un fonds sans recalcul."""
    fonds_col = cols["fonds"]
    montant_col = cols.get("montant_ue")
    montant_total = float(df[montant_col].sum()) if montant_col else 0.0
    lignes = []
    for fonds, sous in df.groupby(fonds_col):
        montant = float(sous[montant_col].sum()) if montant_col else None
        lignes.append({
            "fonds": str(fonds),
            "nb": len(sous),
            "montant_ue": montant,
            "part_nb": _taux(len(sous), n),
            "part_montant": _taux(montant, montant_total) if montant_total and montant else 0.0,
        })
    lignes.sort(key=lambda ligne: (ligne["montant_ue"] or 0), reverse=True)
    return lignes


def _programmes(df, cols):
    col = cols["programme"]
    return {"distincts": int(df[col].nunique()), "top": _valeurs_top(df, col, 20)}


def _regions(df, cols, n):
    """Complétude et ventilation de la colonne région *brute* — volontairement
    distincte de `region_derivable` : ici on décrit la colonne telle quelle, sans
    la dérivation qui la corrige."""
    col = cols["region"]
    remplis = int(df[col].notna().sum())
    profil = {
        "colonne_remplie": remplis,
        "taux_colonne_remplie": _taux(remplis, n),
        "valeurs_distinctes": int(df[col].nunique()),
        "top": _valeurs_top(df, col, 25),
    }
    if "fonds" in cols:
        # Régions manquantes ventilées par fonds : montre *quels* fonds sont
        # concernés (2014-2020 : surtout les programmes nationaux type FEAD).
        manquantes = df[df[col].isna()]
        profil["manquantes_par_fonds"] = _valeurs_top(manquantes, cols["fonds"], 10)
    return profil


def _region_derivable(df, cols, deriver_region):
    """Part des opérations dont la région est récupérable depuis le programme.

    `deriver_region(programme)` renvoie une région, ou None quand le programme
    n'a pas de région unique — cas des programmes nationaux et interrégionaux,
    qui n'en ont pas *par construction* (ce n'est pas un défaut de donnée). Les
    programmes sans région dérivée sont donc listés à part, sans les qualifier
    d'erreur : c'est à la lecture qu'on distingue le national/interrégional
    attendu d'un éventuel trou de mapping.

    `operations_couvertes` combine les deux voies (colonne renseignée **ou**
    programme dérivable) : c'est le seul chiffre qui dit combien d'opérations
    sont réellement rattachables à une région. Selon la période, c'est l'une ou
    l'autre voie qui porte l'essentiel — 2014-2020 dépend du programme, 2021-2027
    de la colonne — et aucune des deux prise seule n'est l'indicateur utile.
    """
    prog_col = cols["programme"]
    programmes = df[prog_col].dropna().unique()
    avec_region = {prog for prog in programmes if deriver_region(prog) is not None}
    derivable = df[prog_col].isin(avec_region)
    resolues = int(derivable.sum())
    n = len(df)
    profil = {
        "programmes_distincts": len(programmes),
        "programmes_avec_region": len(avec_region),
        "operations_resolues": resolues,
        "taux_operations_resolues": _taux(resolues, n),
        "programmes_sans_region_unique": sorted(str(p) for p in programmes if p not in avec_region),
    }
    if "region" in cols:
        couvertes = int((df[cols["region"]].notna() | derivable).sum())
        profil["operations_couvertes"] = couvertes
        profil["taux_operations_couvertes"] = _taux(couvertes, n)
        profil["operations_sans_region"] = n - couvertes
    return profil


def _dimension_thematique(df, cols, n):
    """Champ thématique (domaine/catégorie d'intervention, objectif…). Peut être
    vide à 100 % — auquel cas `taux_remplie` = 0 et `top` est vide, ce qui est
    précisément l'information à afficher."""
    col = cols["dimension_thematique"]
    remplis = int(df[col].notna().sum())
    return {
        "libelle": col,
        "taux_remplie": _taux(remplis, n),
        "distincts": int(df[col].nunique()),
        "top": _valeurs_top(df, col, 10),
    }


def _dates(df, cols):
    """Ventilation par année de la date qui marque l'entrée d'une opération.

    Le `libelle` est repris tel quel parce que ce n'est pas la même date d'une
    période à l'autre — « Date de programmation » en 2014-2020, « Date première
    convention » en 2021-2027. La page nomme ce qu'elle montre plutôt que de
    supposer l'une des deux.
    """
    col = cols["date_programmation"]
    dates = pd.to_datetime(df[col], errors="coerce")
    valides = dates.dropna()
    par_annee = valides.dt.year.value_counts().sort_index()
    return {
        "libelle": col,
        "illisibles": int(dates.isna().sum()),
        "annee_min": int(valides.dt.year.min()) if len(valides) else None,
        "annee_max": int(valides.dt.year.max()) if len(valides) else None,
        "par_annee": {str(int(annee)): int(nb) for annee, nb in par_annee.items()},
    }


def _montants(df, cols):
    ue_col, dep_col = cols["montant_ue"], cols["depenses"]
    total_ue = float(df[ue_col].sum())
    total_dep = float(df[dep_col].sum())
    return {
        "montant_ue_total": total_ue,
        "depenses_total": total_dep,
        "cofinancement_global": round(100 * total_ue / total_dep, 1) if total_dep else None,
        "montants_ue_negatifs": int((df[ue_col] < 0).sum()),
    }


def _cle(df, cols):
    col = cols["numero_operation"]
    return {
        "colonne": col,
        "distincts": int(df[col].nunique()),
        "doublons": int(df[col].duplicated().sum()),
    }


def _valeurs_top(df, col, k):
    """Top k valeurs (hors NaN) sous forme de liste ordonnée [{valeur, nb}]."""
    comptes = df[col].value_counts().head(k)
    return [{"valeur": str(valeur), "nb": int(nb)} for valeur, nb in comptes.items()]
