"""Rattachement des opérations à un département, calculé une fois par le pipeline.

Les champs de localisation ont des formats hétérogènes (cf. `parse_departement_field`,
`zone_dept`) : la cascade les essaie dans l'ordre de fiabilité et note laquelle a
tranché. `ingest.py` écrit le résultat dans le Parquet (colonnes `dept` et
`dept_source`) ; Streamlit et dbt/Metabase lisent ces colonnes au lieu de
recalculer (#232, ADR 002 étape 2).

Jusqu'à #232, cette normalisation vivait dans `dashboard/utils/departments.py`,
« propre à l'affichage du dashboard » : Metabase n'avait donc pas le département,
et le SQL ferait mal cette cascade. Les colonnes d'entrée viennent de
`schema_source` (clés `departement`, `zone`, `cp_beneficiaire`, `nom_benef`), qui
nomme la colonne réelle de chaque source ; une source qui n'en a pas certaines
passe simplement à l'étape suivante.
"""

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPARTEMENTS_GEOJSON_PATH = REPO_ROOT / "data" / "geo" / "departements.geojson"

# Origine du rattachement, dans l'ordre de la cascade. Contrat avec le dashboard,
# qui affiche ces libellés et les importe d'ici (#232).
DEPT_SOURCES = ("opération", "zone", "approximé", "nom du bénéficiaire", "inconnu")

# Clés `schema_source` lues par la cascade.
CLES_ENTREE = ("departement", "zone", "cp_beneficiaire", "nom_benef")

# Alias pour variantes/coquilles observées dans le champ "Département de l'opération"
NAME_ALIASES = {
    "Haute Loire": "Haute-Loire",
    "Pyrénées-Orientiales": "Pyrénées-Orientales",
}

DOM_NAME_TO_CODE = {
    "Guadeloupe": "971",
    "Martinique": "972",
    "Guyane": "973",
    "La Réunion": "974",
    "Mayotte": "976",
}

# Dernier repli quand ni le champ pipeline ni le code postal du bénéficiaire ne permettent de
# rattacher un département (typiquement la Corse : cp_to_dept renvoie None pour tout code postal
# préfixé "20", ambigu entre 2A/2B) : mention explicite et non ambiguë d'une ville/du département
# dans le nom du bénéficiaire. Volontairement restreint aux cas évidents (préfectures, noms de
# département explicites) plutôt qu'une géolocalisation approximative de toutes les communes.
NAME_KEYWORDS_TO_DEPT = {
    "corse-du-sud": "2A",
    "corse du sud": "2A",
    "haute-corse": "2B",
    "haute corse": "2B",
    "ajaccio": "2A",
    "bastia": "2B",
    "porto-vecchio": "2A",
    "porto vecchio": "2A",
    "corte": "2B",
}


def _dept_from_name(nom_beneficiaire):
    if not nom_beneficiaire or not isinstance(nom_beneficiaire, str):
        return None
    nom_lower = nom_beneficiaire.lower()
    for keyword, dept in NAME_KEYWORDS_TO_DEPT.items():
        if keyword in nom_lower:
            return dept
    return None


def _load_name_to_code():
    with open(DEPARTEMENTS_GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)
    name_to_code = {f["properties"]["nom"]: f["properties"]["code"] for f in geojson["features"]}
    name_to_code.update(DOM_NAME_TO_CODE)
    return name_to_code


NAME_TO_CODE = _load_name_to_code()


def _normalize_numeric_code(code):
    if code.isdigit():
        if len(code) == 3 and code.startswith("0"):
            return code[1:]
        return code
    return code.upper().lstrip("0") or code.upper()


def parse_departement_field(raw):
    """Parse le champ "Département de l'opération". Deux formats coexistent dans les
    données : "CODE/Nom | CODE/Nom" (segments avec code explicite) et des segments sans
    code, listant un ou plusieurs noms séparés par des virgules ("Ain, Loire"). Retourne
    la liste des codes département identifiés (dédupliqués), ou [] si vide/non reconnu."""
    if not raw or not isinstance(raw, str):
        return []

    codes = []
    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if "/" in segment:
            code = segment.split("/", 1)[0].strip()
            codes.append(_normalize_numeric_code(code))
        else:
            for name in segment.split(","):
                name = name.strip()
                name = NAME_ALIASES.get(name, name)
                if name in NAME_TO_CODE:
                    codes.append(NAME_TO_CODE[name])

    return sorted(set(codes))


def _commune_code_to_dept(code):
    """Déduit le département depuis un code INSEE commune (5 caractères, DOM inclus,
    Corse en 2A/2B) — même convention que cp_to_dept, avec la Corse en plus."""
    if code[:2] == "97":
        return _normalize_numeric_code(code[:3])
    return _normalize_numeric_code(code[:2])


def zone_dept(raw):
    """Parse le champ "Zone" (Synergie), un champ hiérarchique à préfixe couvrant plusieurs
    granularités : REG/xx (région), DEPT/xxx (département), COMM/xxxxx (commune, code INSEE
    réel), ARRDT/CANT/QUAR (arrondissement/canton/quartier, sous forme de codes eux aussi
    dérivés de l'INSEE — un chiffre/deux chiffres de moins que la commune selon le niveau) —
    plus PAYS, hors de portée. Retourne le département si tous les segments ≥ département
    s'accordent sur un seul, None sinon (vide, seulement REG/PAYS, ou désaccord entre
    segments — cas non observé sur les données réelles mais pas exclu par le format).

    Validé sur les 24 908 opérations 2014-2020 et les 16 625 de 2021-2027 : accord à 100 %
    (3 219 + 665 cas comparables, zéro désaccord) avec "Département de l'opération", le champ
    pipeline déjà tenu pour fiable — Zone porte donc la même localisation (lieu du projet),
    pas celle du bénéficiaire. Contrairement à cp_to_dept, résout la Corse sans ambiguïté
    (COMM/2A004, DEPT/02A... : l'alpha est déjà dans le code source, pas déduit).
    """
    if not raw or not isinstance(raw, str):
        return None
    codes = set()
    for segment in raw.split("|"):
        segment = segment.strip()
        if "/" not in segment:
            continue
        prefix, rest = segment.split("/", 1)
        code = rest.split("/", 1)[0]
        if prefix == "DEPT":
            codes.add(_normalize_numeric_code(code))
        elif prefix == "COMM":
            codes.add(_commune_code_to_dept(code))
        elif prefix == "ARRDT":
            codes.add(_normalize_numeric_code(code[:-1]))
        elif prefix == "CANT":
            codes.add(_normalize_numeric_code(code[:3]))
        elif prefix == "QUAR":
            codes.add(_commune_code_to_dept(code[:5]))
        # REG, PAYS : granularité insuffisante pour un département, segment ignoré.
    return codes.pop() if len(codes) == 1 else None


def cp_to_dept(code_postal):
    """Déduit le code département depuis un code postal français. Approximation : la
    Corse (préfixe "20") n'est pas résolue en 2A/2B à partir du seul code postal."""
    if not code_postal or not isinstance(code_postal, str):
        return None
    cp = code_postal.strip()
    if not cp.isdigit():
        return None
    cp = cp.zfill(5)
    if cp[:2] == "97":
        return cp[:3]
    if cp[:2] == "20":
        return None
    return cp[:2]


def rattacher_departement(departement=None, zone=None, cp_beneficiaire=None, nom_benef=None):
    """Rattache une opération à un département. Priorité au champ "Département de
    l'opération" quand il désigne un département unique (fiable) ; à défaut, au champ "Zone"
    (fiable aussi — cf. zone_dept, même localisation quand les deux sont présents) ; à
    défaut, approxime via le code postal du bénéficiaire (siège du bénéficiaire, pas
    nécessairement le lieu du projet) ; en dernier recours, déduit du nom du bénéficiaire
    quand il mentionne explicitement une ville/le département (cas de la Corse notamment,
    où le code postal seul ne permet pas de distinguer 2A/2B — Zone la résout déjà à
    l'étape précédente quand elle est renseignée). Retourne (code_departement | None,
    source) avec source dans DEPT_SOURCES."""
    codes = parse_departement_field(departement)
    if len(codes) == 1:
        return codes[0], "opération"

    dept = zone_dept(zone)
    if dept:
        return dept, "zone"

    dept = cp_to_dept(cp_beneficiaire)
    if dept:
        return dept, "approximé"

    dept = _dept_from_name(nom_benef)
    if dept:
        return dept, "nom du bénéficiaire"

    return None, "inconnu"


def ajouter_departements(df, cols):
    """`df` avec les colonnes `dept` et `dept_source`.

    `cols` : {clé schema_source -> colonne réelle de la source}. Une clé absente
    (la source n'a pas ce champ) vaut None pour toutes les lignes."""
    df = df.copy()
    entrees = {
        cle: (df[cols[cle]] if cle in cols and cols[cle] in df.columns else pd.Series(None, index=df.index))
        for cle in CLES_ENTREE
    }
    rattachements = [
        rattacher_departement(*valeurs)
        for valeurs in zip(*(entrees[cle] for cle in CLES_ENTREE), strict=True)
    ]
    # strict=True : chaque rattachement est un couple (code, source) — un retour à
    # l'arité différente tronquerait les deux colonnes sans rien signaler.
    df["dept"], df["dept_source"] = zip(*rattachements, strict=True) if len(df) else ([], [])
    return df
