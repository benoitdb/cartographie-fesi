import pandas as pd


def _code_valide_pour_territoire(code, territoire, lookup):
    """Un code postal n'est utilisable que s'il est à la fois connu du référentiel ET rattaché
    au territoire demandé — un simple préfixe à 3 chiffres ne suffit pas : Saint-Martin partage
    le préfixe 971 avec la Guadeloupe (rattachement au circuit postal guadeloupéen, code 97150),
    donc un bénéficiaire basé à Saint-Martin sur une opération classée région Guadeloupe (cas
    réel observé : "Collectivité de Saint-Martin", 4 opérations) se serait sinon retrouvé
    positionné sur la carte de la Guadeloupe. isinstance(code, str) : region_ops passe par
    DataFrame.to_dict("records") côté appelant, qui remplace les None manquants par NaN (float)
    dans une colonne à dtype mixte — un NaN est "truthy" en Python, donc un simple `if code`
    ne suffit pas à l'écarter avant l'accès au dict."""
    return isinstance(code, str) and code in lookup and lookup[code]["territoire"] == territoire


def _resoudre_code_postal(op, territoire, lookup):
    """Code postal le plus fiable pour localiser une opération sur la carte, ou None si
    aucun n'est exploitable. Priorité au code postal de l'opération elle-même (lieu réel du
    projet, ~30% des cas pour les DROM-COM) ; à défaut, celui du bénéficiaire (siège du porteur
    de projet, pas nécessairement le lieu de réalisation — même approximation que pour le
    rattachement département en métropole)."""
    cp_operation = op.get("Code postal de l’opération")
    if _code_valide_pour_territoire(cp_operation, territoire, lookup):
        return cp_operation, "opération"
    cp_beneficiaire = op.get("Code postal du bénéficiaire")
    if _code_valide_pour_territoire(cp_beneficiaire, territoire, lookup):
        return cp_beneficiaire, "bénéficiaire (approximé)"
    return None, "non localisable"


def build_bubbles_localisation(region_ops, territoire, lookup, amount_col="Montant UE"):
    """Agrège les opérations d'un territoire DROM-COM par code postal résolu (une bulle par
    code postal, pas un point par opération — évite la surcharge visuelle et reste lisible sur
    un territoire de petite taille). Retourne (bubbles_df, couverture) où couverture est un
    dict {"opération": n, "bénéficiaire (approximé)": n, "non localisable": n}."""
    resolus = [(*_resoudre_code_postal(op, territoire, lookup), op) for op in region_ops]

    couverture = {"opération": 0, "bénéficiaire (approximé)": 0, "non localisable": 0}
    lignes = []
    for code_postal, source, op in resolus:
        couverture[source] += 1
        if code_postal is None:
            continue
        lignes.append({"code_postal": code_postal, "source": source, amount_col: op.get(amount_col) or 0})

    if not lignes:
        return pd.DataFrame(columns=["code_postal", "commune", "lat", "lon", "count", amount_col]), couverture

    df = pd.DataFrame(lignes)
    agg = df.groupby("code_postal").agg(count=(amount_col, "count"), **{amount_col: (amount_col, "sum")}).reset_index()
    agg["commune"] = agg["code_postal"].map(lambda cp: lookup[cp]["commune"])
    agg["lat"] = agg["code_postal"].map(lambda cp: lookup[cp]["lat"])
    agg["lon"] = agg["code_postal"].map(lambda cp: lookup[cp]["lon"])
    return agg.sort_values(amount_col, ascending=False), couverture
