"""
Maquettes REACT-EU par programme opérationnel, FEDER et FSE.

Source primaire : "Évaluation de l'initiative REACT-EU en France — Rapport final",
Agence nationale de la cohésion des territoires (ANCT), 20 décembre 2024, tableaux
"État d'avancement des PO Français sur le volet REACT-EU FEDER" (p.8-9) et "État
d'avancement des PO Français REACT-EU FSE" (p.10), colonne **Maquette UE**. PDF fourni
manuellement par l'utilisateur. Transcrit le 2026-08-25 ; `_verifier_totaux()` revalide
la transcription à chaque import contre les lignes TOTAL des deux tableaux.

**Pourquoi un fichier distinct de `programmes_2014_2020.py`.** L'Accord de partenariat
2014-2020 est antérieur à REACT-EU (version 4 validée en octobre 2019, REACT-EU créé par
le règlement 2020/2221 en décembre 2020) : il ne mentionne aucune ressource REACT-EU. Les
montants ci-dessous ont donc une provenance et une nature différentes, qui ne doivent pas
se confondre avec celles des dotations de l'Accord :

- ce sont des **maquettes constatées en fin de période**, après les décisions
  modificatives de programme, et non des dotations préliminaires arrêtées en amont ;
- elles viennent d'un **rapport d'évaluation**, pas d'un texte réglementaire. Le document
  précise lui-même que ses chiffres de certification sont estimés, arrêtés au
  24 septembre 2024. Les maquettes, elles, sont les enveloppes des programmes à cette date.

Pour un taux de consommation c'est une bonne nouvelle — le dénominateur est celui de la
fin de période, cohérent avec des opérations engagées jusqu'en 2023 — mais la mention de
provenance doit rester visible à l'écran, distincte de celle de l'Accord.

**Le rapprochement se fait par CCI**, que le rapport ne porte pas : il nomme les
programmes à sa façon ("PO FEDER-FSE Aquitaine" pour le programme que l'Accord appelle
"PO FEDER-FSE Nouvelle Aquitaine", "PO Réunion Etat", "PO Franche-Comté"…). Le CCI de
chaque ligne a donc été rattaché à la main au programme correspondant de
`programmes_2014_2020.PROGRAMMES`, et `_verifier_totaux()` contrôle que tous les CCI
utilisés y existent bien.

**Un programme par région fusionnée.** La Commission n'a autorisé la modification que
d'**un seul** programme par région issue d'une fusion : en Auvergne-Rhône-Alpes tout
REACT-EU passe par le PO Rhône-Alpes, alors que les projets financés couvrent aussi
l'ex-Auvergne (même chose en Normandie et Grand Est, dit le rapport p.7). Agréger ces
maquettes par région **moderne** est donc non seulement possible mais correct ; les
répartir entre anciennes régions n'aurait aucun sens.

**`montant_justifie`** vient de la colonne « Montant justifié après le dernier appel de
fonds au 24 septembre 2024 » des mêmes tableaux (p.8-11) — un taux de consommation
REACT-EU indépendant des opérations Synergie, utile là où le libellé de fonds ne l'est
pas (voir MAPPING_FONDS_DONNEES et issue #96). Le rapport publie ces montants avec des
centimes ; ils sont arrondis à l'euro ici, par cohérence avec le reste du fichier — d'où
un écart d'arrondi cumulé de ±1 € entre la somme des lignes et le total publié à la
ligne TOTAL, documenté et toléré dans `_verifier_totaux()`, pas une erreur de
transcription.

**Corroboration** : `docs/sources/allocation_react_eu_regions_2021_2022.pdf` (DGCL/ANCT,
22/03/2021, allocation initiale par région) donne des totaux régionaux FEDER et FSE qui
recoupent exactement la somme des lignes ci-dessous par région — hors deux programmes
guadeloupéens où 10 M€ et 2 M€ ont basculé du FEDER vers le FSE entre 2021 et 2024 (le
total par programme, lui, ne bouge pas). Un indice de plus que la transcription est
juste, pas une source alternative à lire par le code.
"""

from collections import namedtuple

from reference.programmes_2014_2020 import programme

# `fonds` est le fonds au sens du rapport : "FEDER" ou "FSE". Ce n'est pas le libellé
# porté par les opérations engagées — voir MAPPING_FONDS_DONNEES plus bas, où se joue
# toute la différence de traitement entre les deux.
Maquette = namedtuple("Maquette", "cci fonds montant_ue montant_justifie nom_rapport")

MAQUETTES = [
    # Volet FEDER — 25 programmes (p.8-9)
    Maquette("2014FR16M0OP008", "FEDER", 88_934_928, 102_275_167, "PO FEDER-FSE Picardie 2014-2020"),
    Maquette("2014FR16M2OP001", "FEDER", 115_720_121, 133_078_139, "PO FEDER-FSE Basse-Normandie 2014-2020"),
    Maquette("2014FR16RFOP002", "FEDER", 7_822_019, 8_995_322, "PO Interrégional FEDER Loire 2014-2020"),
    Maquette("2014FR16M2OP009", "FEDER", 56_752_747, 65_106_315, "PO FEDER-FSE Poitou Charentes 2014-2020"),
    Maquette("2014FR16M2OP010", "FEDER", 160_539_061, 184_147_420, "PO FEDER-FSE Rhône-Alpes 2014-2020"),
    Maquette("2014FR16M0OP014", "FEDER", 52_103_383, 59_618_294, "PO FEDER-FSE Bourgogne 2014-2020"),
    Maquette("2014FR05M0OP001", "FEDER", 101_321_953, 114_924_356, "PO FEDER-FSE Ile-de-France et Bassin de Seine 2014-2020"),
    Maquette("2014FR16M0OP007", "FEDER", 111_405_335, 123_969_500, "PO FEDER-FSE Midi-Pyrénées et Garonne 2014-2020"),
    Maquette("2014FR16M2OP006", "FEDER", 30_630_366, 33_973_782, "PO FEDER-FSE Limousin 2014-2020"),
    Maquette("2014FR16M2OP003", "FEDER", 92_779_237, 101_127_972, "PO FEDER-FSE Bretagne 2014-2020"),
    Maquette("2014FR16M0OP015", "FEDER", 173_425_967, 183_909_853, "PO FEDER-FSE Lorraine et Vosges 2014-2020"),
    Maquette("2014FR16M0OP013", "FEDER", 95_044_857, 100_517_723, "PO FEDER-FSE Provence Alpes Côte d'Azur 2014-2020"),
    Maquette("2014FR16M2OP008", "FEDER", 67_369_800, 68_763_091, "PO FEDER-FSE Pays de la Loire 2014-2020"),
    Maquette("2014FR16M0OP012", "FEDER", 177_879_806, 179_227_435, "PO FEDER-FSE Nord-Pas de Calais 2014-2020"),
    Maquette("2014FR16M2OP005", "FEDER", 50_903_209, 51_193_917, "PO FEDER-FSE Franche-Comté et Massif du Jura 2014-2020"),
    Maquette("2014FR16M0OP003", "FEDER", 89_557_007, 89_563_819, "PO FEDER-FSE Centre Val-de-Loire 2014-2020"),
    Maquette("2014FR16M0OP001", "FEDER", 97_473_702, 93_886_506, "PO FEDER-FSE Aquitaine 2014-2020"),
    Maquette("2014FR16M0OP006", "FEDER", 87_532_761, 84_243_065, "PO FEDER-FSE Languedoc-Roussillon 2014-2020"),
    Maquette("2014FR16RFOP007", "FEDER", 340_948_106, 251_236_518, "PO FEDER Réunion Conseil Régional 2014-2020"),
    Maquette("2014FR16M2OP012", "FEDER", 119_115_539, 80_384_080, "PO FEDER-FSE Mayotte Etat 2014-2020"),
    Maquette("2014FR16M2OP004", "FEDER", 31_996_069, 17_100_558, "PO FEDER-FSE Corse 2014-2020"),
    Maquette("2014FR16M0OP009", "FEDER", 170_169_923, 77_495_075, "PO FEDER-FSE Guadeloupe Conseil Régional 2014-2020"),
    Maquette("2014FR16M2OP011", "FEDER", 133_534_305, 45_283_708, "PO FEDER-FSE Guyane Conseil Régional 2014-2020"),
    Maquette("2014FR05M2OP001", "FEDER", 34_231_733, 7_224_874, "PO FEDER-FSE Guadeloupe et st Martin Etat 2014-2020"),
    Maquette("2014FR16M0OP011", "FEDER", 159_103_812, 31_544_730, "PO FEDER-FSE Martinique Conseil Régional 2014-2020"),

    # Volet FSE — 16 programmes (p.10)
    Maquette("2014FR16M0OP004", "FSE", 12_350_060, 14_202_569, "PO FEDER-FSE Champagne-Ardenne 2014-2020"),
    Maquette("2014FR05SFOP001", "FSE", 800_060_179, 894_847_747, "PO National FSE Emploi et Inclusion 2014-2020"),
    Maquette("2014FR16M0OP014", "FSE", 5_200_000, 5_396_291, "PO FEDER-FSE Bourgogne 2014-2020"),
    Maquette("2014FR16M2OP008", "FSE", 19_000_000, 19_000_000, "PO FEDER-FSE Pays de la Loire 2014-2020"),
    Maquette("2014FR16M2OP005", "FSE", 7_280_000, 7_225_548, "PO FEDER-FSE Franche-Comté et Massif du Jura 2014-2020"),
    Maquette("2014FR05SFOP003", "FSE", 31_526_760, 30_901_308, "PO FSE Guyane Etat 2014-2020"),
    Maquette("2014FR05SFOP005", "FSE", 148_094_472, 130_489_351, "PO FSE Réunion Etat 2014-2020"),
    Maquette("2014FR16M2OP010", "FSE", 28_439_941, 24_944_948, "PO FEDER-FSE Rhône-Alpes 2014-2020"),
    Maquette("2014FR16M0OP013", "FSE", 40_625_000, 29_216_166, "PO FEDER-FSE Provence Alpes Côte d'Azur 2014-2020"),
    Maquette("2014FR16M2OP009", "FSE", 7_217_693, 4_988_641, "PO FEDER-FSE Poitou Charentes 2014-2020"),
    Maquette("2014FR16M2OP012", "FSE", 20_000_000, 12_828_614, "PO FEDER-FSE Mayotte Etat 2014-2020"),
    Maquette("2014FR16M0OP001", "FSE", 10_846_859, 6_420_677, "PO FEDER-FSE Aquitaine 2014-2020"),
    Maquette("2014FR16M2OP006", "FSE", 5_635_448, 2_785_445, "PO FEDER-FSE Limousin 2014-2020"),
    Maquette("2014FR05SFOP004", "FSE", 38_830_420, 18_964_883, "PO FSE Martinique Etat 2014-2020"),
    Maquette("2014FR05M2OP001", "FSE", 31_570_048, 0, "PO FEDER-FSE Guadeloupe et Saint-Martin Etat 2014-2020"),
    Maquette("2014FR16M0OP009", "FSE", 9_000_000, 0, "PO FEDER-FSE Guadeloupe Conseil Régional 2014-2020"),
]

# Lignes TOTAL des deux tableaux. Le rapport imprime le total FEDER "2 646 295,746,00 €",
# avec une virgule de trop au milieu — coquille de mise en forme du document : la somme
# des 25 lignes vaut bien 2 646 295 746, ce que vérifie `_verifier_totaux()`.
_TOTAUX_PUBLIES = {"FEDER": 2_646_295_746, "FSE": 1_215_676_880}

# Mêmes lignes TOTAL, colonne « Montant justifié » : 2 288 791 218,40 € et
# 1 202 212 187,75 € dans le rapport. Arrondis à l'euro puis comparés à la somme des
# montants ci-dessus avec une tolérance de 1 € par volet — l'arrondi ligne à ligne peut
# dévier de l'arrondi du total (25 et 16 arrondis indépendants, pas un seul), ce qui
# n'est pas la même chose qu'une ligne mal transcrite.
_TOTAUX_JUSTIFIES_PUBLIES = {"FEDER": 2_288_791_218, "FSE": 1_202_212_188}
_TOLERANCE_ARRONDI_JUSTIFIE = 1

# Comment chaque volet se rapproche des opérations engagées. Cette table porte le point
# le plus contre-intuitif de la période :
#
# - le volet **FEDER** a son propre libellé de fonds dans les données (`FEDER REACT-EU`,
#   593 opérations dans l'extraction Synergie) : sa maquette est donc une enveloppe
#   distincte, à ne surtout pas ajouter à celle du FEDER de l'Accord ;
# - le volet **FSE** n'en a **pas** : les opérations REACT-EU FSE sont indiscernables des
#   autres opérations FSE dans la source (issue #82). Sa maquette doit donc être *ajoutée*
#   à la dotation FSE de l'Accord, faute de quoi le dénominateur FSE ignore 1 215,7 M€ que
#   le numérateur, lui, contient.
#
# Traiter les deux volets pareil produit une erreur dans un sens ou dans l'autre selon le
# choix fait : c'est pour ça que la règle est écrite ici plutôt que déduite au cas par cas.
MAPPING_FONDS_DONNEES = {"FEDER": "FEDER REACT-EU", "FSE": "FSE"}


def _verifier_totaux():
    par_fonds = {}
    for m in MAQUETTES:
        par_fonds[m.fonds] = par_fonds.get(m.fonds, 0) + m.montant_ue
    assert par_fonds.keys() == _TOTAUX_PUBLIES.keys(), (
        f"Volets transcrits {sorted(par_fonds)} != volets contrôlés {sorted(_TOTAUX_PUBLIES)}"
    )
    for fonds, publie in _TOTAUX_PUBLIES.items():
        calcule = par_fonds[fonds]
        assert calcule == publie, f"Total REACT-EU {fonds} : calculé={calcule} publié={publie} (écart {calcule - publie:+})"

    par_fonds_justifie = {}
    for m in MAQUETTES:
        par_fonds_justifie[m.fonds] = par_fonds_justifie.get(m.fonds, 0) + m.montant_justifie
    for fonds, publie in _TOTAUX_JUSTIFIES_PUBLIES.items():
        calcule = par_fonds_justifie[fonds]
        ecart = calcule - publie
        assert abs(ecart) <= _TOLERANCE_ARRONDI_JUSTIFIE, (
            f"Total justifié REACT-EU {fonds} : calculé={calcule} publié={publie} (écart {ecart:+}, "
            f"tolérance {_TOLERANCE_ARRONDI_JUSTIFIE} € d'arrondi cumulé)"
        )

    # Le rapport annonce 25 programmes FEDER et 16 FSE dans ses tableaux (son texte parle
    # de "24 maquettes" et "15 maquettes", en ne comptant pas les programmes gérés par
    # une préfecture — Mayotte et Guadeloupe État). Compter les lignes protège d'un oubli
    # que les totaux ne verraient pas si deux lignes se compensaient.
    assert len([m for m in MAQUETTES if m.fonds == "FEDER"]) == 25, "volet FEDER : 25 lignes attendues"
    assert len([m for m in MAQUETTES if m.fonds == "FSE"]) == 16, "volet FSE : 16 lignes attendues"

    vus = set()
    for m in MAQUETTES:
        programme(m.cci)  # lève si le CCI n'existe pas dans l'Accord de partenariat
        assert (m.cci, m.fonds) not in vus, f"Maquette en double : {m.cci}/{m.fonds}"
        vus.add((m.cci, m.fonds))


_verifier_totaux()
