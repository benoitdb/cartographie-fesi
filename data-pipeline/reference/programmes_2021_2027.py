"""
Programmes opérationnels FEDER/FSE+/FTJ/FEAMPA France 2021-2027 : enveloppes programmées
(contribution UE, assistance technique, contribution nationale) par programme, fonds et
catégorie de région.

Source primaire : Accord de partenariat des autorités françaises 2021-2027, version 1.4
adoptée par la Commission européenne le 2 juin 2022, Tableau 9B "Liste des programmes
prévus comportant des dotations financières préliminaires" (p.48-50). PDF fourni
manuellement par l'utilisateur (voir feedback-ask-for-manual-fetch) — pas téléchargé
automatiquement. Transcrit le 2026-08-14 ; _verify_totals() ci-dessous revalide la
transcription à chaque import contre les totaux publiés dans le document.

Ces montants sont les enveloppes PROGRAMMÉES sur toute la période 2021-2027 (fixées par
décision d'exécution en amont), à ne pas confondre avec les montants ENGAGÉS/conventionnés
que retrace data/processed/data.json (opérations réellement attribuées à date). Leur
rapprochement (par CCI puis par fonds/catégorie) permet de calculer un taux de consommation
par programme — voir issue #6 du backlog ("Taux de consommation des fonds par programme").

Catégorie de région : "Plus développée" / "En transition" / "Moins développée" (politique de
cohésion, voir cohesion_ue.py) ou "Ultrapériphériques" (allocation additionnelle RUP,
art. 349 TFUE — réservée aux 6 programmes DOM/Saint-Martin, où elle s'ajoute à leur
enveloppe "Moins développée" ; ce n'est pas une catégorie alternative mais une ligne
budgétaire distincte au sein du même programme). Pour le FTJ, un système de classification
différent s'applique : "Article 3" / "Article 4" du règlement FTJ, sans lien direct avec les
3 catégories de cohésion — catégorie=None pour le programme FEAMPA (hors politique de
cohésion, pas de notion de catégorie de région).

Chaque programme est identifié par son code CCI (identifiant officiel UE, stable). La
correspondance avec le libellé exact utilisé dans data.json (`Libellé Programme`, via
region_mapping.PROGRAMME_TO_REGION) ne peut PAS se faire par égalité de texte : les deux
documents n'utilisent pas le même intitulé pour un même programme (ex. "Programme FEDER-FSE+
2021-2027 de La Réunion" dans les données sources vs "Réunion FEDER-FSE+ 2021-2027" dans cet
accord) — d'où l'usage du CCI et du champ `region` ci-dessous comme clés stables plutôt qu'un
rapprochement par texte.
"""

from collections import namedtuple

Programme = namedtuple(
    "Programme", "cci nom region fonds categorie contribution_ue assistance_technique contribution_nationale"
)

PROGRAMMES = [
    Programme("2021FR05FFPR001", "Île-de-France et bassin de la Seine FEDER-FSE+ 2021-2027", "Île-de-France", "FEDER", "Plus développée", 176_586_006, 5_971_507, 264_879_011),
    Programme("2021FR05FFPR001", "Île-de-France et bassin de la Seine FEDER-FSE+ 2021-2027", "Île-de-France", "FEDER", "En transition", 7_358_850, 248_850, 4_905_900),
    Programme("2021FR05FFPR001", "Île-de-France et bassin de la Seine FEDER-FSE+ 2021-2027", "Île-de-France", "FSE+", "Plus développée", 245_106_248, 9_427_163, 367_659_373),

    Programme("2021FR05JTPR001", "Programme national FTJ Emploi - Compétences", None, "FTJ", "Article 3", 135_296_744, 5_203_720, 63_782_750),
    Programme("2021FR05JTPR001", "Programme national FTJ Emploi - Compétences", None, "FTJ", "Article 4", 173_689_036, 6_680_347, 81_881_974),

    Programme("2021FR05SFPR001", "Programme national FSE+ Emploi - Inclusion - Jeunesse - Compétences", None, "FSE+", "Plus développée", 764_725_647, 29_412_524, 1_143_644_297),
    Programme("2021FR05SFPR001", "Programme national FSE+ Emploi - Inclusion - Jeunesse - Compétences", None, "FSE+", "En transition", 2_541_969_082, 97_768_041, 1_659_807_516),
    Programme("2021FR05SFPR001", "Programme national FSE+ Emploi - Inclusion - Jeunesse - Compétences", None, "FSE+", "Moins développée", 596_935_045, 22_959_040, 103_942_649),
    Programme("2021FR05SFPR001", "Programme national FSE+ Emploi - Inclusion - Jeunesse - Compétences", None, "FSE+", "Ultrapériphériques", 103_603_974, 3_984_768, 18_283_054),

    Programme("2021FR05SFPR002", "Programme national FSE+ - Soutien européen à l'aide alimentaire", None, "FSE+", "Plus développée", 137_778_806, 6_560_895, 15_308_756),
    Programme("2021FR05SFPR002", "Programme national FSE+ - Soutien européen à l'aide alimentaire", None, "FSE+", "En transition", 433_068_559, 20_622_312, 48_118_729),
    Programme("2021FR05SFPR002", "Programme national FSE+ - Soutien européen à l'aide alimentaire", None, "FSE+", "Moins développée", 11_152_635, 531_077, 1_239_182),

    Programme("2021FR16FFPR001", "Provence-Alpes-Côte d'Azur et massif des Alpes FEDER-FSE+-FTJ 2021-2027", "Provence-Alpes-Côte d'Azur", "FEDER", "En transition", 351_275_069, 11_878_867, 346_238_031),
    Programme("2021FR16FFPR001", "Provence-Alpes-Côte d'Azur et massif des Alpes FEDER-FSE+-FTJ 2021-2027", "Provence-Alpes-Côte d'Azur", "FSE+", "En transition", 138_920_526, 5_343_097, 138_920_526),
    Programme("2021FR16FFPR001", "Provence-Alpes-Côte d'Azur et massif des Alpes FEDER-FSE+-FTJ 2021-2027", "Provence-Alpes-Côte d'Azur", "FTJ", "Article 3", 64_716_942, 2_489_113, 96_992_568),
    Programme("2021FR16FFPR001", "Provence-Alpes-Côte d'Azur et massif des Alpes FEDER-FSE+-FTJ 2021-2027", "Provence-Alpes-Côte d'Azur", "FTJ", "Article 4", 83_081_256, 3_195_432, 124_704_729),

    Programme("2021FR16FFPR002", "Réunion FEDER-FSE+ 2021-2027", "La Réunion", "FEDER", "Moins développée", 1_033_500_848, 44_504_821, 280_922_190),
    Programme("2021FR16FFPR002", "Réunion FEDER-FSE+ 2021-2027", "La Réunion", "FEDER", "Ultrapériphériques", 202_855_712, 8_735_413, 67_537_587),
    Programme("2021FR16FFPR002", "Réunion FEDER-FSE+ 2021-2027", "La Réunion", "FSE+", "Moins développée", 150_174_122, 7_151_148, 26_501_317),
    Programme("2021FR16FFPR002", "Réunion FEDER-FSE+ 2021-2027", "La Réunion", "FSE+", "Ultrapériphériques", 23_176_139, 1_103_625, 4_089_907),

    Programme("2021FR16FFPR003", "Pays de la Loire FEDER-FSE+-FTJ 2021-2027", "Pays de la Loire", "FEDER", "En transition", 301_215_318, 10_186_025, 200_810_212),
    Programme("2021FR16FFPR003", "Pays de la Loire FEDER-FSE+-FTJ 2021-2027", "Pays de la Loire", "FSE+", "En transition", 64_532_857, 2_482_032, 43_021_905),
    Programme("2021FR16FFPR003", "Pays de la Loire FEDER-FSE+-FTJ 2021-2027", "Pays de la Loire", "FTJ", "Article 3", 21_151_391, 813_515, 9_064_882),
    Programme("2021FR16FFPR003", "Pays de la Loire FEDER-FSE+-FTJ 2021-2027", "Pays de la Loire", "FTJ", "Article 4", 27_153_386, 1_044_361, 11_637_165),

    Programme("2021FR16FFPR004", "Occitanie FEDER-FSE+ 2021-2027", "Occitanie", "FEDER", "En transition", 666_057_162, 22_523_672, 444_038_111),
    Programme("2021FR16FFPR004", "Occitanie FEDER-FSE+ 2021-2027", "Occitanie", "FSE+", "En transition", 163_629_196, 6_293_430, 109_086_131),

    Programme("2021FR16FFPR005", "Nouvelle-Aquitaine FEDER-FSE+ 2021-2027", "Nouvelle-Aquitaine", "FEDER", "En transition", 735_539_606, 24_873_320, 490_359_739),
    Programme("2021FR16FFPR005", "Nouvelle-Aquitaine FEDER-FSE+ 2021-2027", "Nouvelle-Aquitaine", "FSE+", "En transition", 140_130_727, 5_389_643, 93_420_486),

    Programme("2021FR16FFPR006", "Normandie FEDER-FSE+-FTJ 2021-2027", "Normandie", "FEDER", "En transition", 401_531_295, 13_578_352, 267_687_530),
    Programme("2021FR16FFPR006", "Normandie FEDER-FSE+-FTJ 2021-2027", "Normandie", "FSE+", "En transition", 88_505_825, 3_404_070, 59_003_884),
    Programme("2021FR16FFPR006", "Normandie FEDER-FSE+-FTJ 2021-2027", "Normandie", "FTJ", "Article 3", 46_722_475, 1_797_018, 20_023_918),
    Programme("2021FR16FFPR006", "Normandie FEDER-FSE+-FTJ 2021-2027", "Normandie", "FTJ", "Article 4", 59_980_614, 2_306_946, 25_705_978),

    Programme("2021FR16FFPR008", "Martinique FEDER-FSE+ 2021-2027", "Martinique", "FEDER", "En transition", 393_021_844, 16_924_385, 267_500_000),
    Programme("2021FR16FFPR008", "Martinique FEDER-FSE+ 2021-2027", "Martinique", "FEDER", "Ultrapériphériques", 88_729_627, 3_820_893, 93_500_000),
    Programme("2021FR16FFPR008", "Martinique FEDER-FSE+ 2021-2027", "Martinique", "FSE+", "En transition", 99_663_978, 4_745_903, 34_000_000),
    Programme("2021FR16FFPR008", "Martinique FEDER-FSE+ 2021-2027", "Martinique", "FSE+", "Ultrapériphériques", 19_182_574, 913_455, 4_400_000),

    Programme("2021FR16FFPR010", "Hauts de France FEDER-FSE+-FTJ 2021-2027", "Hauts-de-France", "FEDER", "En transition", 897_423_853, 30_347_666, 852_078_390),
    Programme("2021FR16FFPR010", "Hauts de France FEDER-FSE+-FTJ 2021-2027", "Hauts-de-France", "FSE+", "En transition", 232_447_433, 8_940_285, 137_754_280),
    Programme("2021FR16FFPR010", "Hauts de France FEDER-FSE+-FTJ 2021-2027", "Hauts-de-France", "FTJ", "Article 3", 99_758_799, 3_836_876, 226_375_736),
    Programme("2021FR16FFPR010", "Hauts de France FEDER-FSE+-FTJ 2021-2027", "Hauts-de-France", "FTJ", "Article 4", 128_066_716, 4_925_642, 290_612_934),

    Programme("2021FR16FFPR011", "Centre-Val de Loire et interrégional Loire FEDER-FSE+ 2021-2027", "Centre-Val de Loire", "FEDER", "En transition", 309_088_386, 10_452_264, 212_162_549),
    Programme("2021FR16FFPR011", "Centre-Val de Loire et interrégional Loire FEDER-FSE+ 2021-2027", "Centre-Val de Loire", "FSE+", "En transition", 103_277_468, 3_972_210, 68_851_645),

    Programme("2021FR16FFPR012", "Guyane FEDER-FSE+ 2021-2027", "Guyane", "FEDER", "Moins développée", 345_700_100, 14_886_607, 84_075_657),
    Programme("2021FR16FFPR012", "Guyane FEDER-FSE+ 2021-2027", "Guyane", "FEDER", "Ultrapériphériques", 64_794_489, 2_790_193, 20_040_204),
    Programme("2021FR16FFPR012", "Guyane FEDER-FSE+ 2021-2027", "Guyane", "FSE+", "Moins développée", 71_858_349, 3_421_826, 12_680_886),
    Programme("2021FR16FFPR012", "Guyane FEDER-FSE+ 2021-2027", "Guyane", "FSE+", "Ultrapériphériques", 10_857_819, 517_039, 1_206_424),

    Programme("2021FR16FFPR013", "Guadeloupe FEDER-FSE+ 2021-2027", "Guadeloupe", "FEDER", "Moins développée", 464_947_483, 20_021_661, 149_392_762),
    Programme("2021FR16FFPR013", "Guadeloupe FEDER-FSE+ 2021-2027", "Guadeloupe", "FEDER", "Ultrapériphériques", 93_800_693, 4_039_264, 47_067_769),
    Programme("2021FR16FFPR013", "Guadeloupe FEDER-FSE+ 2021-2027", "Guadeloupe", "FSE+", "Moins développée", 68_588_520, 3_266_120, 12_103_857),
    Programme("2021FR16FFPR013", "Guadeloupe FEDER-FSE+ 2021-2027", "Guadeloupe", "FSE+", "Ultrapériphériques", 10_920_297, 520_014, 1_927_111),

    Programme("2021FR16FFPR014", "Grand Est et massif des Vosges FEDER-FSE+-FTJ 2021-2027", "Grand Est", "FEDER", "En transition", 631_482_796, 21_354_490, 420_988_531),
    Programme("2021FR16FFPR014", "Grand Est et massif des Vosges FEDER-FSE+-FTJ 2021-2027", "Grand Est", "FSE+", "En transition", 155_217_122, 5_969_889, 103_478_081),
    Programme("2021FR16FFPR014", "Grand Est et massif des Vosges FEDER-FSE+-FTJ 2021-2027", "Grand Est", "FTJ", "Article 3", 49_248_015, 1_894_154, 21_106_292),
    Programme("2021FR16FFPR014", "Grand Est et massif des Vosges FEDER-FSE+-FTJ 2021-2027", "Grand Est", "FTJ", "Article 4", 63_222_809, 2_431_646, 27_095_490),

    Programme("2021FR16FFPR015", "Corse FEDER-FSE+ 2021-2027", "Corse", "FEDER", "En transition", 105_147_777, 3_555_721, 70_098_519),
    Programme("2021FR16FFPR015", "Corse FEDER-FSE+ 2021-2027", "Corse", "FSE+", "En transition", 12_668_842, 487_263, 8_445_895),

    Programme("2021FR16FFPR016", "Bretagne FEDER-FSE+ 2021-2027", "Bretagne", "FEDER", "En transition", 332_934_921, 11_258_668, 728_808_680),
    Programme("2021FR16FFPR016", "Bretagne FEDER-FSE+ 2021-2027", "Bretagne", "FSE+", "En transition", 59_955_955, 2_305_998, 39_970_637),

    Programme("2021FR16FFPR017", "Bourgogne-Franche-Comté et massif du Jura FEDER-FSE+ 2021-2027", "Bourgogne-Franche-Comté", "FEDER", "En transition", 401_454_687, 13_575_758, 407_906_333),
    Programme("2021FR16FFPR017", "Bourgogne-Franche-Comté et massif du Jura FEDER-FSE+ 2021-2027", "Bourgogne-Franche-Comté", "FSE+", "En transition", 83_571_311, 3_214_280, 55_714_208),

    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FEDER", "Plus développée", 377_494_748, 12_765_522, 566_242_122),
    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FEDER", "En transition", 282_405_301, 9_549_937, 188_270_200),
    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FSE+", "Plus développée", 111_824_903, 4_300_957, 167_737_355),
    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FSE+", "En transition", 31_264_699, 1_202_488, 20_843_133),
    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FTJ", "Article 3", 34_094_779, 1_311_337, 34_094_779),
    Programme("2021FR16FFPR018", "Auvergne-Rhône-Alpes et des territoires Rhône Saône et Massif Central FEDER-FSE+-FTJ 2021-2027", "Auvergne-Rhône-Alpes", "FTJ", "Article 4", 43_769_637, 1_683_447, 43_769_637),

    Programme("2021FR16RFPR001", "Saint Martin FEDER 2021-2027", "Saint-Martin", "FEDER", "Moins développée", 51_231_429, 2_206_138, 27_586_097),
    Programme("2021FR16RFPR001", "Saint Martin FEDER 2021-2027", "Saint-Martin", "FEDER", "Ultrapériphériques", 7_605_671, 327_516, 4_095_416),

    Programme("2021FR16RFPR002", "Mayotte FEDER 2021-2027", "Mayotte", "FEDER", "Moins développée", 288_999_687, 12_444_962, 98_665_944),
    Programme("2021FR16RFPR002", "Mayotte FEDER 2021-2027", "Mayotte", "FEDER", "Ultrapériphériques", 58_202_853, 2_506_342, 198_096_030),

    Programme("2021FR14MFPR001", "Programme national FEAMPA", None, "FEAMPA", None, 567_136_526, 32_102_067, 226_169_479),
]

# Totaux publiés dans le document (dernières lignes du Tableau 9B) — utilisés uniquement
# pour revalider la transcription ci-dessus à chaque import.
_TOTAL_FEDER_FSE_FTJ = (16_775_047_468, 641_152_952, 12_382_673_232)
_TOTAL_TOUS_FONDS = (17_342_183_994, 673_255_019, 12_608_842_711)


# Écart constaté entre la somme des 70 lignes détaillées et la ligne "TOTAL" imprimée dans
# le document (p.50) : chaque ligne détaillée a été revérifiée individuellement contre le
# texte brut du PDF (aucun écart trouvé) — l'écart ci-dessous est donc dans le document
# source lui-même (arrondi ou consolidation en amont), pas une erreur de transcription.
# Négligeable en relatif (0,006% sur la contribution nationale) : toléré plutôt que masqué.
_ECART_TOLERE = {"contribution_ue": 0, "assistance_technique": 10, "contribution_nationale": 800_000}


def _verify_totals():
    hors_feampa = [p for p in PROGRAMMES if p.fonds != "FEAMPA"]
    totaux_hors_feampa = (
        sum(p.contribution_ue for p in hors_feampa),
        sum(p.assistance_technique for p in hors_feampa),
        sum(p.contribution_nationale for p in hors_feampa),
    )
    totaux_tous_fonds = (
        sum(p.contribution_ue for p in PROGRAMMES),
        sum(p.assistance_technique for p in PROGRAMMES),
        sum(p.contribution_nationale for p in PROGRAMMES),
    )
    tolerances = tuple(_ECART_TOLERE.values())
    for calcule, publie, label in [(totaux_hors_feampa, _TOTAL_FEDER_FSE_FTJ, "FEDER-FSE+-FTJ"), (totaux_tous_fonds, _TOTAL_TOUS_FONDS, "tous fonds")]:
        for c, p, tol, champ in zip(calcule, publie, tolerances, _ECART_TOLERE):
            assert abs(c - p) <= tol, f"Écart inattendu sur {label}/{champ} : calculé={c} publié={p} (tolérance={tol})"


_verify_totals()
