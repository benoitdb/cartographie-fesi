"""
Dotations financières programmées par objectif stratégique (OS1-OS5) et objectif spécifique
FTJ, au niveau NATIONAL uniquement — voir issue #21.

Source primaire : Accord de partenariat des autorités françaises 2021-2027, version 1.4
adoptée par la Commission européenne le 2 juin 2022, Tableau 8 "Dotation financière
provisoire émanant du FEDER, du FC, du FSE+, du FEAMPA et du FTJ par objectif stratégique et
assistance technique" (p.46-47). PDF fourni manuellement par l'utilisateur (voir
feedback-ask-for-manual-fetch) — pas téléchargé automatiquement. Transcrit le 2026-08-17.

Contrairement au Tableau 9B (programmes_2021_2027.py), ce tableau ne ventile PAS par région
nommée — seulement par catégorie de région (Plus développées / En transition / Moins
développées / Ultrapériphériques), au niveau national agrégé. Une dotation programmée par
région ET par objectif stratégique existerait dans le Programme Opérationnel propre à chaque
région (document distinct de l'Accord de partenariat), mais pas dans ce document — voir
issue #28 pour l'exploration de cette piste (chantier futur, effort jugé disproportionné pour
une itération courte : 19 documents à trouver, structure non uniforme d'une région à l'autre,
correspondance Priorité régionale → OS UE pas fiable par simple numéro).

Seules les enveloppes FEDER et FSE+ sont retenues ci-dessous (FEAMPA hors périmètre du
dashboard, voir issue #14 — comme dans programmes_2021_2027.py). La ligne "Assistance
technique" du Tableau 8 est délibérément exclue : c'est une ligne à part dans le document
(pas une sous-catégorie d'un objectif stratégique), et aucune opération de data.json n'est
classée sous "assistance technique" dans le champ Objectif stratégique (vérifié : 0 occurrence
sur 16625 opérations) — l'inclure fausserait la comparaison programmé vs engagé.

Clés alignées sur les valeurs exactes du champ "Objectif stratégique" de data.json (issues du
fichier source SYNERGIE), pour un rapprochement direct sans table de correspondance
supplémentaire. Le FTJ n'est pas un objectif stratégique au même titre que OS1-OS5 (c'est un
fonds à part, avec son propre "objectif spécifique" dans le Tableau 8) mais partage la même
dimension de regroupement côté data.json ("8. Transition juste").
"""

# Dotation nationale FEDER par objectif stratégique, avec le détail par catégorie de région tel
# qu'imprimé dans le Tableau 8 (revalidé ci-dessous : la somme des 4 catégories doit égaler la
# dotation nationale de chaque ligne).
_FEDER_PAR_OS = {
    "1. Europe plus intelligente": {
        "national": 3_530_900_606,
        "Plus développées": 259_400_000, "En transition": 2_467_403_698,
        "Moins développées": 690_523_821, "Ultrapériphériques": 113_573_087,
    },
    "2. Europe plus verte": {
        "national": 3_332_774_035,
        "Plus développées": 214_714_499, "En transition": 2_039_747_082,
        "Moins développées": 918_704_135, "Ultrapériphériques": 159_608_319,
    },
    "3. Europe plus connectée": {
        "national": 270_058_298,
        "Plus développées": 0, "En transition": 27_610_856,
        "Moins développées": 46_929_724, "Ultrapériphériques": 195_517_718,
    },
    "4. Europe plus sociale": {
        "national": 552_090_047,
        "Plus développées": 21_000_000, "En transition": 173_614_778,
        "Moins développées": 332_404_969, "Ultrapériphériques": 25_070_300,
    },
    "5. Europe plus proche des citoyens": {
        "national": 1_049_234_411,
        "Plus développées": 40_229_226, "En transition": 907_252_476,
        "Moins développées": 101_752_709, "Ultrapériphériques": 0,
    },
}

# Dotation nationale FSE+ par objectif stratégique — la France concentre tout son FSE+
# national sur l'OS4 uniquement (0 sur OS1/2/3/5, confirmé par le Tableau 8 lui-même).
_FSE_PAR_OS = {
    "4. Europe plus sociale": {
        "national": 6_408_498_074,
        "Plus développées": 1_209_734_068, "En transition": 4_176_682_642,
        "Moins développées": 861_379_462, "Ultrapériphériques": 160_701_902,
    },
}

# Objectif spécifique FTJ (fonds à part, hors OS1-5) — Article 3/4 du règlement FTJ, même
# classification que ftj_article dans programme_totals.py.
DOTATION_FTJ = {"Article 3": 433_643_410, "Article 4": 556_695_628}

# Dotation par OS, éclatée par fonds contributeur — nécessaire pour recalculer un total
# "programmé" cohérent avec le filtre Fonds actif dans le dashboard (un OS où seul le FEDER
# contribue ne doit pas apparaître à 0% consommé si l'utilisateur désélectionne le FEDER,
# alors qu'aucune opération de ce fonds n'est simplement affichée — même logique que
# programme_totals.py pour le filtre par région).
DOTATIONS_OS_PAR_FONDS = {
    os: {
        **({"FEDER": _FEDER_PAR_OS[os]["national"]} if os in _FEDER_PAR_OS else {}),
        **({"FSE+": _FSE_PAR_OS[os]["national"]} if os in _FSE_PAR_OS else {}),
    }
    for os in _FEDER_PAR_OS
}
DOTATIONS_OS_PAR_FONDS["8. Transition juste"] = {"FTJ": sum(DOTATION_FTJ.values())}

DOTATIONS_OS = {os: sum(montants.values()) for os, montants in DOTATIONS_OS_PAR_FONDS.items()}


def _verify_totals():
    for source, label in [(_FEDER_PAR_OS, "FEDER"), (_FSE_PAR_OS, "FSE+")]:
        for os, montants in source.items():
            categories = [v for k, v in montants.items() if k != "national"]
            assert sum(categories) == montants["national"], f"{label}/{os} : somme des catégories ({sum(categories)}) != national ({montants['national']})"

    # Cross-validation contre programmes_2021_2027.py (Tableau 9B, transcrit et vérifié
    # indépendamment le 2026-08-14) : la somme des dotations par OS + FTJ ci-dessus doit
    # égaler le total FEDER+FSE+FTJ du Tableau 9B, contribution UE moins assistance technique
    # (l'AT est exclue ici, voir docstring). Petit écart de rounding toléré, même ordre de
    # grandeur que _ECART_TOLERE dans programmes_2021_2027.py.
    from reference.programmes_2021_2027 import _TOTAL_FEDER_FSE_FTJ

    total_contribution_ue, total_assistance_technique, _ = _TOTAL_FEDER_FSE_FTJ
    attendu = total_contribution_ue - total_assistance_technique
    calcule = sum(DOTATIONS_OS.values())
    assert abs(calcule - attendu) <= 10, f"Écart inattendu OS vs Tableau 9B : calculé={calcule} attendu={attendu}"


_verify_totals()
