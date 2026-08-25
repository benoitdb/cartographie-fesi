"""
Programmes opérationnels FEDER/FSE/IEJ France 2014-2020 : dotations programmées
(contribution UE) par programme, fonds et année.

Source primaire : Accord de partenariat des autorités françaises 2014-2020, version 4
validée le 16 octobre 2019, section 1.6 "Liste des programmes FEDER et FSE, sauf ceux
relatifs à l'objectif de coopération territoriale européenne, et des programmes FEADER et
FEAMP, avec leurs allocations indicatives respectives, par fonds et par année"
(p.165-173). PDF fourni manuellement par l'utilisateur — pas téléchargé automatiquement.
Transcrit le 2026-08-25 ; `_verifier_totaux()` revalide la transcription à chaque import
contre les totaux publiés par le document lui-même.

Pendant 2014-2020 de `programmes_2021_2027.py` (Tableau 9B), avec quatre différences :

1. **Pas de catégorie de région.** En 2014-2020 les programmes sont bâtis par *ancienne*
   région, chacune d'une seule catégorie de cohésion : la catégorie est une propriété du
   programme, pas une ligne budgétaire interne. Le rattachement se fait donc ailleurs
   (`nuts_2014_2020.py` + `cohesion_ue_2014_2020.py`, décision 2014/99/UE), pas ici.
2. **Pas d'assistance technique ni de contrepartie nationale par ligne** : la table 1.6 ne
   donne que la contribution UE. L'assistance technique interfonds a son propre programme
   (Europ'Act, CCI 2014FR16M2TA001), présent ci-dessous comme les autres.
3. **Une ventilation par année** (2014 → 2020), que 2021-2027 n'a pas. Chaque ligne se
   contrôle seule : la somme des sept années redonne son total.
4. **FEADER et FEAMP sont hors périmètre** : ils figurent dans la table du document mais
   pas dans les données du dashboard. Seuls FEDER, FSE et IEJ sont transcrits.

Deux fonds présents dans les opérations engagées n'ont **aucune** ligne ici, et c'est
normal :

- **FEAD** — ce n'est pas un Fonds ESI mais un transfert hors enveloppe structurelle
  (art. 94 du règlement 1303/2013), régi par le règlement 223/2014 et absent de l'Accord.
- **FEDER REACT-EU** — l'Accord est antérieur à REACT-EU (validé en 2019, REACT-EU créé
  en 2020). Ses maquettes vivent dans `react_eu_2014_2020.py`, dont la provenance est
  différente et doit le rester.

Attention à l'IEJ : voir `ALLOCATION_SPECIFIQUE_IEJ` plus bas — la ligne `IEJ` d'un
programme n'est que la moitié de sa ressource IEJ.

Chaque programme est identifié par son **code CCI**, comme en 2021-2027 et pour la même
raison : les libellés diffèrent d'un document à l'autre (le Rapport d'évaluation REACT-EU
écrit "PO FEDER-FSE Aquitaine" là où l'Accord écrit "PO FEDER-FSE Nouvelle Aquitaine", et
Synergie "Programme opérationnel régional Auvergne FEDER-FSE 2014-2020"). Le CCI, lui, est
stable — et les données engagées le portent (colonne `NumCCI`).
"""

from collections import namedtuple

# Un programme opérationnel. `region` est la région **moderne** (post-2016) de
# rattachement, ou None pour les programmes nationaux et interrégionaux — même
# convention que region_mapping.PROGRAMME_TO_REGION_2014_2020. Ce rattachement ne peut
# pas se contrôler ici — cette table-là est indexée par libellé Synergie, pas par CCI :
# il est éprouvé dans tests/test_programmes_2014_2020.py contre un relevé indépendant,
# saisi à la main, comme l'exige déjà le schéma de source (voir CLAUDE.md).
Programme = namedtuple("Programme", "cci nom region")

# Une ligne de la table 1.6 : un programme, un fonds, le total sur la période et sa
# ventilation annuelle 2014 → 2020 (7 valeurs).
Dotation = namedtuple("Dotation", "cci fonds montant_ue ventilation")

ANNEES = (2014, 2015, 2016, 2017, 2018, 2019, 2020)

PROGRAMMES = [
    Programme("2014FR05M0OP001", "PO FEDER-FSE Ile-de-France et Bassin de Seine", "Île-de-France"),
    Programme("2014FR05M2OP001", "PO FEDER-FSE Guadeloupe et st Martin Etat", "Guadeloupe"),
    Programme("2014FR05M9OP001", "PO National pour la mise en œuvre de l'IEJ en métropole et outre-mer", None),
    Programme("2014FR05M9OP002", "PO FSE Alsace", "Grand Est"),
    Programme("2014FR05SFOP001", "PO National FSE Emploi et Inclusion", None),
    Programme("2014FR05SFOP003", "PO FSE Guyane Etat", "Guyane"),
    Programme("2014FR05SFOP004", "PO FSE Martinique Etat", "Martinique"),
    Programme("2014FR05SFOP005", "PO FSE Réunion Etat", "La Réunion"),
    Programme("2014FR16M0OP001", "PO FEDER-FSE Nouvelle Aquitaine", "Nouvelle-Aquitaine"),
    Programme("2014FR16M0OP002", "PO FEDER-FSE Auvergne", "Auvergne-Rhône-Alpes"),
    Programme("2014FR16M0OP003", "PO FEDER-FSE Centre", "Centre-Val de Loire"),
    Programme("2014FR16M0OP004", "PO FEDER-FSE Champagne-Ardenne", "Grand Est"),
    Programme("2014FR16M0OP005", "PO FEDER-FSE Haute Normandie", "Normandie"),
    Programme("2014FR16M0OP006", "PO FEDER-FSE Languedoc-Roussillon", "Occitanie"),
    Programme("2014FR16M0OP007", "PO FEDER-FSE Midi-Pyrénées et Garonne", "Occitanie"),
    Programme("2014FR16M0OP008", "PO FEDER-FSE Picardie", "Hauts-de-France"),
    Programme("2014FR16M0OP009", "PO FEDER-FSE Guadeloupe CR", "Guadeloupe"),
    Programme("2014FR16M0OP011", "PO FEDER-FSE Martinique CR", "Martinique"),
    Programme("2014FR16M0OP012", "PO FEDER-FSE Nord-Pas de Calais", "Hauts-de-France"),
    Programme("2014FR16M0OP013", "PO FEDER-FSE Provence Alpes Côte d'Azur", "Provence-Alpes-Côte d'Azur"),
    Programme("2014FR16M0OP014", "PO FEDER-FSE Bourgogne", "Bourgogne-Franche-Comté"),
    Programme("2014FR16M0OP015", "PO FEDER-FSE Lorraine et Vosges", "Grand Est"),
    Programme("2014FR16M2OP001", "PO FEDER-FSE Basse-Normandie", "Normandie"),
    Programme("2014FR16M2OP003", "PO FEDER-FSE Bretagne", "Bretagne"),
    Programme("2014FR16M2OP004", "PO FEDER-FSE Corse", "Corse"),
    Programme("2014FR16M2OP005", "PO FEDER-FSE Franche-Comté et massif du Jura", "Bourgogne-Franche-Comté"),
    Programme("2014FR16M2OP006", "PO FEDER-FSE Limousin", "Nouvelle-Aquitaine"),
    Programme("2014FR16M2OP008", "PO FEDER-FSE Pays de la Loire", "Pays de la Loire"),
    Programme("2014FR16M2OP009", "PO FEDER-FSE Poitou Charentes", "Nouvelle-Aquitaine"),
    Programme("2014FR16M2OP010", "PO FEDER-FSE Rhône-Alpes", "Auvergne-Rhône-Alpes"),
    Programme("2014FR16M2OP011", "PO FEDER-FSE Guyane CR", "Guyane"),
    Programme("2014FR16M2OP012", "PO FEDER-FSE Mayotte", "Mayotte"),
    Programme("2014FR16M2TA001", "PO National d'Assistance Technique Interfonds Europ'Act", None),
    Programme("2014FR16RFOP001", "POI Alpes", None),
    Programme("2014FR16RFOP002", "POI Loire", None),
    Programme("2014FR16RFOP003", "POI Massif Central", None),
    Programme("2014FR16RFOP004", "POI Pyrénées", None),
    Programme("2014FR16RFOP005", "POI Rhône Saône", None),
    Programme("2014FR16RFOP006", "PO FEDER Alsace", "Grand Est"),
    Programme("2014FR16RFOP007", "PO FEDER Réunion CR", "La Réunion"),
]

DOTATIONS = [
    Dotation("2014FR05M0OP001", "FEDER", 185_396_968, (24_936_878, 25_436_135, 25_945_316, 26_464_577, 26_994_214, 27_534_434, 28_085_414)),
    Dotation("2014FR05M0OP001", "FSE", 294_203_032, (39_571_874, 40_364_136, 41_172_144, 41_996_150, 42_836_621, 43_693_885, 44_568_222)),
    Dotation("2014FR05M0OP001", "IEJ", 3_957_370, (1_624_924, 1_257_215, 0, 448_013, 313_609, 209_073, 104_536)),
    Dotation("2014FR05M2OP001", "FEDER", 38_614_896, (5_193_909, 5_297_896, 5_403_949, 5_512_101, 5_622_415, 5_734_933, 5_849_693)),
    Dotation("2014FR05M2OP001", "FSE", 157_185_104, (17_362_516, 19_227_023, 24_710_075, 21_871_285, 24_153_484, 24_667_986, 25_192_735)),
    Dotation("2014FR05M9OP001", "FSE", 331_418_831, (122_280_957, 95_688_363, 0, 47_270_632, 22_059_626, 22_059_627, 22_059_626)),
    Dotation("2014FR05M9OP001", "IEJ", 329_418_831, (121_143_332, 94_825_988, 0, 47_270_632, 33_089_439, 22_059_627, 11_029_813)),
    Dotation("2014FR05M9OP002", "FSE", 46_252_510, (6_221_209, 6_345_763, 6_472_792, 6_602_336, 6_734_469, 6_869_242, 7_006_699)),
    Dotation("2014FR05M9OP002", "IEJ", 4_485_714, (0, 0, 0, 1_869_047, 1_308_334, 872_222, 436_111)),
    Dotation("2014FR05SFOP001", "FSE", 2_820_495_562, (324_378_876, 351_133_631, 426_256_323, 404_233_369, 429_230_238, 438_105_526, 447_157_599)),
    Dotation("2014FR05SFOP003", "FSE", 78_956_069, (8_818_684, 9_765_694, 12_550_619, 10_741_833, 12_096_688, 12_358_012, 12_624_539)),
    Dotation("2014FR05SFOP004", "FSE", 119_706_536, (13_107_151, 14_514_685, 18_653_899, 16_946_623, 18_437_078, 18_825_481, 19_221_619)),
    Dotation("2014FR05SFOP005", "FSE", 501_107_323, (54_325_187, 60_158_998, 77_314_794, 72_305_230, 77_380_538, 78_990_351, 80_632_225)),
    Dotation("2014FR16M0OP001", "FEDER", 368_699_392, (49_592_028, 50_584_903, 51_597_511, 52_630_168, 53_683_459, 54_757_794, 55_853_529)),
    Dotation("2014FR16M0OP001", "FSE", 80_520_608, (10_830_450, 11_047_285, 11_268_430, 11_493_952, 11_723_981, 11_958_606, 12_197_904)),
    Dotation("2014FR16M0OP001", "IEJ", 10_054_123, (5_668_424, 4_385_699, 0, 0, 0, 0, 0)),
    Dotation("2014FR16M0OP002", "FEDER", 215_442_139, (28_978_113, 29_558_280, 30_149_977, 30_753_389, 31_368_859, 31_996_625, 32_636_896)),
    Dotation("2014FR16M0OP002", "FSE", 34_467_861, (4_636_110, 4_728_930, 4_823_593, 4_920_131, 5_018_598, 5_119_032, 5_221_467)),
    Dotation("2014FR16M0OP002", "IEJ", 6_069_483, (3_421_920, 2_647_563, 0, 0, 0, 0, 0)),
    Dotation("2014FR16M0OP003", "FEDER", 179_865_447, (24_192_858, 24_677_221, 25_171_209, 25_674_978, 26_188_813, 26_712_914, 27_247_454)),
    Dotation("2014FR16M0OP003", "FSE", 63_654_553, (8_561_876, 8_733_292, 8_908_115, 9_086_399, 9_268_246, 9_453_725, 9_642_900)),
    Dotation("2014FR16M0OP003", "IEJ", 16_418_623, (6_523_815, 5_047_521, 0, 2_019_703, 1_413_792, 942_528, 471_264)),
    Dotation("2014FR16M0OP004", "FEDER", 181_550_137, (24_419_458, 24_908_357, 25_406_972, 25_915_460, 26_434_107, 26_963_117, 27_502_666)),
    Dotation("2014FR16M0OP004", "FSE", 41_289_863, (5_553_706, 5_664_897, 5_778_296, 5_893_942, 6_011_898, 6_132_208, 6_254_916)),
    Dotation("2014FR16M0OP004", "IEJ", 8_377_612, (2_989_014, 2_312_621, 0, 1_281_657, 897_160, 598_107, 299_053)),
    Dotation("2014FR16M0OP005", "FEDER", 226_243_976, (30_431_017, 31_040_273, 31_661_636, 32_295_303, 32_941_631, 33_600_872, 34_273_244)),
    Dotation("2014FR16M0OP005", "FSE", 55_436_024, (7_456_440, 7_605_725, 7_757_976, 7_913_241, 8_071_609, 8_233_142, 8_397_891)),
    Dotation("2014FR16M0OP005", "IEJ", 12_164_363, (4_482_635, 3_468_246, 0, 1_755_618, 1_228_932, 819_288, 409_644)),
    Dotation("2014FR16M0OP006", "FEDER", 305_969_459, (41_154_519, 41_978_468, 42_818_792, 43_675_754, 44_549_840, 45_441_389, 46_350_697)),
    Dotation("2014FR16M0OP006", "FSE", 105_080_541, (14_133_892, 14_416_865, 14_705_461, 14_999_771, 15_299_962, 15_606_151, 15_918_439)),
    Dotation("2014FR16M0OP006", "IEJ", 20_636_793, (7_720_911, 5_973_722, 0, 2_892_566, 2_024_798, 1_349_864, 674_932)),
    Dotation("2014FR16M0OP007", "FEDER", 384_359_334, (51_698_372, 52_733_420, 53_789_037, 54_865_553, 55_963_582, 57_083_548, 58_225_822)),
    Dotation("2014FR16M0OP007", "FSE", 73_180_666, (9_843_189, 10_040_258, 10_241_244, 10_446_209, 10_655_269, 10_868_506, 11_085_991)),
    Dotation("2014FR16M0OP007", "IEJ", 3_624_568, (1_435_980, 1_111_027, 0, 448_983, 314_289, 209_525, 104_764)),
    Dotation("2014FR16M0OP008", "FEDER", 219_703_414, (29_551_277, 30_142_919, 30_746_320, 31_361_667, 31_989_310, 32_629_493, 33_282_428)),
    Dotation("2014FR16M0OP008", "FSE", 72_346_586, (9_731_001, 9_925_824, 10_124_519, 10_327_147, 10_533_825, 10_744_632, 10_959_638)),
    Dotation("2014FR16M0OP008", "IEJ", 11_234_154, (4_032_615, 3_120_063, 0, 1_700_616, 1_190_430, 793_620, 396_810)),
    Dotation("2014FR16M0OP009", "FEDER", 521_846_279, (70_191_119, 71_596_398, 73_029_606, 74_491_191, 75_981_983, 77_502_558, 79_053_424)),
    Dotation("2014FR16M0OP009", "FSE", 86_653_721, (11_655_387, 11_888_737, 12_126_726, 12_369_426, 12_616_976, 12_869_472, 13_126_997)),
    Dotation("2014FR16M0OP009", "IEJ", 3_694_247, (1_240_340, 959_660, 0, 622_602, 435_822, 290_549, 145_274)),
    Dotation("2014FR16M0OP011", "FEDER", 445_101_522, (59_868_541, 61_067_153, 62_289_587, 63_536_225, 64_807_774, 66_104_727, 67_427_515)),
    Dotation("2014FR16M0OP011", "FSE", 73_338_478, (9_864_415, 10_061_910, 10_263_329, 10_468_735, 10_678_247, 10_891_944, 11_109_898)),
    Dotation("2014FR16M0OP011", "IEJ", 3_781_101, (1_416_071, 1_095_624, 0, 528_919, 370_243, 246_829, 123_415)),
    Dotation("2014FR16M0OP012", "FEDER", 673_578_758, (90_599_923, 92_413_812, 94_263_751, 96_150_316, 98_074_579, 100_037_287, 102_039_090)),
    Dotation("2014FR16M0OP012", "FSE", 152_121_242, (20_461_116, 20_870_766, 21_288_556, 21_714_618, 22_149_194, 22_592_452, 23_044_540)),
    Dotation("2014FR16M0OP012", "IEJ", 33_311_957, (12_547_998, 9_708_473, 0, 4_606_452, 3_224_517, 2_149_678, 1_074_839)),
    Dotation("2014FR16M0OP013", "FEDER", 284_316_236, (38_242_045, 39_007_684, 39_788_539, 40_584_855, 41_397_082, 42_225_537, 43_070_494)),
    Dotation("2014FR16M0OP013", "FSE", 146_678_268, (20_010_879, 20_411_514, 20_820_111, 20_363_625, 21_254_330, 21_687_835, 22_129_974)),
    Dotation("2014FR16M0OP014", "FEDER", 183_532_126, (24_686_045, 25_180_283, 25_684_341, 26_198_380, 26_722_690, 27_257_475, 27_802_912)),
    Dotation("2014FR16M0OP014", "FSE", 40_197_874, (5_406_828, 5_515_077, 5_625_478, 5_738_064, 5_852_901, 5_970_031, 6_089_495)),
    Dotation("2014FR16M0OP014", "IEJ", 3_057_397, (0, 0, 0, 1_273_915, 891_741, 594_494, 297_247)),
    Dotation("2014FR16M0OP015", "FEDER", 336_748_799, (45_294_502, 46_201_339, 47_126_196, 48_069_366, 49_031_381, 50_012_617, 51_013_398)),
    Dotation("2014FR16M0OP015", "FSE", 71_791_201, (9_656_298, 9_849_626, 10_046_795, 10_247_869, 10_452_960, 10_662_149, 10_875_504)),
    Dotation("2014FR16M0OP015", "IEJ", 1_188_001, (0, 0, 0, 495_001, 346_500, 231_000, 115_500)),
    Dotation("2014FR16M2OP001", "FEDER", 187_000_606, (25_152_575, 25_656_152, 26_169_736, 26_693_489, 27_227_708, 27_772_600, 28_328_346)),
    Dotation("2014FR16M2OP001", "FSE", 39_829_394, (5_357_265, 5_464_522, 5_573_911, 5_685_466, 5_799_249, 5_915_306, 6_033_675)),
    Dotation("2014FR16M2OP003", "FEDER", 307_307_301, (41_334_465, 42_162_017, 43_006_016, 43_866_725, 44_744_633, 45_640_080, 46_553_365)),
    Dotation("2014FR16M2OP003", "FSE", 62_192_699, (8_365_249, 8_532_728, 8_703_536, 8_877_726, 9_055_396, 9_236_617, 9_421_447)),
    Dotation("2014FR16M2OP004", "FEDER", 104_054_391, (13_995_869, 14_276_078, 14_561_856, 14_853_293, 15_150_553, 15_453_752, 15_762_990)),
    Dotation("2014FR16M2OP004", "FSE", 11_586_065, (1_586_571, 1_618_337, 1_650_733, 1_596_461, 1_676_722, 1_711_093, 1_746_148)),
    Dotation("2014FR16M2OP005", "FEDER", 150_937_387, (20_301_880, 20_708_342, 21_122_881, 21_545_629, 21_976_822, 22_416_631, 22_865_202)),
    Dotation("2014FR16M2OP005", "FSE", 33_572_613, (4_515_695, 4_606_103, 4_698_308, 4_792_338, 4_888_248, 4_986_073, 5_085_848)),
    Dotation("2014FR16M2OP006", "FEDER", 125_558_965, (16_888_348, 17_226_468, 17_571_307, 17_922_973, 18_281_667, 18_647_527, 19_020_675)),
    Dotation("2014FR16M2OP006", "FSE", 19_111_035, (2_570_536, 2_622_000, 2_674_487, 2_728_014, 2_782_610, 2_838_296, 2_895_092)),
    Dotation("2014FR16M2OP008", "FEDER", 302_748_728, (40_721_313, 41_536_589, 42_368_068, 43_216_009, 44_080_894, 44_963_059, 45_862_796)),
    Dotation("2014FR16M2OP008", "FSE", 76_711_272, (10_318_074, 10_524_651, 10_735_333, 10_950_187, 11_169_333, 11_392_858, 11_620_836)),
    Dotation("2014FR16M2OP009", "FEDER", 222_973_695, (29_991_147, 30_591_596, 31_203_978, 31_828_485, 32_465_470, 33_115_183, 33_777_836)),
    Dotation("2014FR16M2OP009", "FSE", 44_976_305, (6_049_551, 6_170_670, 6_294_194, 6_420_164, 6_548_651, 6_679_705, 6_813_370)),
    Dotation("2014FR16M2OP010", "FEDER", 364_091_269, (48_972_211, 49_952_677, 50_952_629, 51_972_379, 53_012_506, 54_073_414, 55_155_453)),
    Dotation("2014FR16M2OP010", "FSE", 145_308_731, (19_544_798, 19_936_101, 20_335_181, 20_742_163, 21_157_277, 21_580_685, 22_012_526)),
    Dotation("2014FR16M2OP011", "FEDER", 338_100_501, (45_476_325, 46_386_796, 47_315_363, 48_262_315, 49_228_189, 50_213_359, 51_218_154)),
    Dotation("2014FR16M2OP011", "FSE", 53_124_352, (7_314_332, 7_460_771, 7_610_121, 7_239_448, 7_673_721, 7_832_175, 7_993_784)),
    Dotation("2014FR16M2OP012", "FEDER", 148_872_908, (20_024_198, 20_425_100, 20_833_969, 21_250_933, 21_676_230, 22_110_022, 22_552_456)),
    Dotation("2014FR16M2OP012", "FSE", 62_641_320, (6_887_517, 7_627_146, 9_802_212, 8_795_985, 9_637_368, 9_841_465, 10_049_627)),
    Dotation("2014FR16M2TA001", "FEDER", 40_829_592, (5_491_796, 5_601_748, 5_713_883, 5_828_240, 5_944_880, 6_063_851, 6_185_194)),
    Dotation("2014FR16M2TA001", "FSE", 31_771_039, (4_273_348, 4_358_911, 4_446_179, 4_535_173, 4_625_947, 4_718_529, 4_812_952)),
    Dotation("2014FR16RFOP001", "FEDER", 34_000_000, (4_573_181, 4_664_740, 4_758_118, 4_853_346, 4_950_476, 5_049_547, 5_150_592)),
    Dotation("2014FR16RFOP002", "FEDER", 33_000_000, (4_438_675, 4_527_542, 4_618_174, 4_710_600, 4_804_874, 4_901_031, 4_999_104)),
    Dotation("2014FR16RFOP003", "FEDER", 40_000_000, (5_380_213, 5_487_929, 5_597_786, 5_709_819, 5_824_090, 5_940_644, 6_059_519)),
    Dotation("2014FR16RFOP004", "FEDER", 24_872_998, (3_235_630, 3_429_956, 3_498_617, 3_568_637, 3_640_056, 3_712_902, 3_787_200)),
    Dotation("2014FR16RFOP005", "FEDER", 33_000_000, (4_438_675, 4_527_542, 4_618_174, 4_710_600, 4_804_874, 4_901_031, 4_999_104)),
    Dotation("2014FR16RFOP006", "FEDER", 87_207_490, (11_729_871, 11_964_713, 12_204_223, 12_448_474, 12_697_606, 12_951_716, 13_210_887)),
    Dotation("2014FR16RFOP007", "FEDER", 1_130_456_061, (152_052_390, 155_096_594, 158_201_300, 161_367_480, 164_596_927, 167_890_894, 171_250_476)),
]

# Totaux publiés par le document, utilisés pour revalider la transcription à chaque
# import : FEDER et FSE en p.145 (table des concours par objectif thématique, ligne
# "Total"), allocation spécifique IEJ en p.146 (§1.4.2). Les trois tombent au centime —
# aucune tolérance n'est nécessaire ici, contrairement au Tableau 9B de 2021-2027.
_TOTAUX_PUBLIES = {"FEDER": 8_425_980_774, "FSE": 6_026_907_278, "IEJ": 471_474_337}

# §1.4.2 de l'Accord (p.146). **Piège central de la période** : la ligne `IEJ` d'un
# programme ne porte que l'allocation spécifique IEJ. Chaque euro d'allocation spécifique
# est accompagné d'un euro de FSE — la "contrepartie FSE" — comptée, elle, sur la ligne
# `FSE` du même programme. La ressource IEJ réelle est donc le double de ce qui figure ici.
#
#     Allocation spécifique IEJ ....... 471 474 337 €
#     Contrepartie FSE ................ 473 185 393 €
#     Total des ressources IEJ ........ 944 659 730 €
#
# Conséquence pour tout rapprochement avec les opérations engagées : le `Montant UE` d'une
# opération IEJ couvre les deux moitiés. La comparer à la seule ligne `IEJ` donne un taux
# de consommation voisin de 200 % (constaté à 203 % et 229 % sur des périmètres réels).
# Voir `dotation_iej_totale()` plus bas, qui fait le calcul correctement.
ALLOCATION_SPECIFIQUE_IEJ = 471_474_337
CONTREPARTIE_FSE_IEJ = 473_185_393

_INDEX_PROGRAMMES = {p.cci: p for p in PROGRAMMES}


def programme(cci):
    """Le programme portant ce CCI. Lève plutôt que de renvoyer None sur un CCI inconnu :
    un CCI absent est une erreur de transcription ou une source nouvelle, pas un trou."""
    if cci not in _INDEX_PROGRAMMES:
        raise KeyError(f"CCI inconnu de l'Accord de partenariat 2014-2020 : {cci!r}")
    return _INDEX_PROGRAMMES[cci]


def dotation_iej_totale(cci):
    """Ressource IEJ d'un programme : allocation spécifique + contrepartie FSE.

    La contrepartie n'est publiée qu'en total national (§1.4.2), jamais par programme.
    Elle est donc répartie **au prorata de l'allocation spécifique** de chaque programme.
    L'hypothèse est celle du règlement IEJ lui-même (art. 22 du règlement 1304/2013 :
    la contrepartie FSE est appariée à l'allocation spécifique), et l'égalité des deux
    totaux nationaux à 0,4 % près la corrobore. Renvoie 0 pour un programme sans IEJ.
    """
    specifique = sum(d.montant_ue for d in DOTATIONS if d.cci == cci and d.fonds == "IEJ")
    if not specifique:
        return 0
    return specifique + round(CONTREPARTIE_FSE_IEJ * specifique / ALLOCATION_SPECIFIQUE_IEJ)


def _verifier_totaux():
    par_fonds = {}
    for d in DOTATIONS:
        par_fonds[d.fonds] = par_fonds.get(d.fonds, 0) + d.montant_ue
    assert par_fonds.keys() == _TOTAUX_PUBLIES.keys(), (
        f"Fonds transcrits {sorted(par_fonds)} != fonds contrôlés {sorted(_TOTAUX_PUBLIES)}"
    )
    for fonds, publie in _TOTAUX_PUBLIES.items():
        calcule = par_fonds[fonds]
        assert calcule == publie, f"Total {fonds} : calculé={calcule} publié={publie} (écart {calcule - publie:+})"

    # Contrôle de forme, distinct du contrôle par totaux : celui-ci ne peut pas voir une
    # ligne rattachée au mauvais programme, puisque la somme reste juste. C'est
    # exactement l'erreur qu'une première transcription avait commise (lignes FEDER
    # accrochées au programme de développement rural imprimé juste au-dessus).
    ccis_dotations = {d.cci for d in DOTATIONS}
    ccis_programmes = {p.cci for p in PROGRAMMES}
    assert ccis_dotations == ccis_programmes, (
        f"CCI sans programme : {sorted(ccis_dotations - ccis_programmes)} ; "
        f"programmes sans dotation : {sorted(ccis_programmes - ccis_dotations)}"
    )
    assert len(ccis_programmes) == len(PROGRAMMES), "CCI dupliqué dans PROGRAMMES"

    for d in DOTATIONS:
        assert len(d.ventilation) == len(ANNEES), f"{d.cci}/{d.fonds} : {len(d.ventilation)} années"
        assert sum(d.ventilation) == d.montant_ue, (
            f"{d.cci}/{d.fonds} : somme des années {sum(d.ventilation)} != total {d.montant_ue}"
        )

    vus = set()
    for d in DOTATIONS:
        assert (d.cci, d.fonds) not in vus, f"Ligne en double : {d.cci}/{d.fonds}"
        vus.add((d.cci, d.fonds))


_verifier_totaux()
