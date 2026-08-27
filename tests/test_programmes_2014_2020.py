"""Les enveloppes programmées 2014-2020 (reference/, programme_totals_2014_2020.py).

Les modules de référence se contrôlent déjà eux-mêmes à l'import, contre les totaux
publiés par leurs documents sources. Ces tests couvrent ce que ce contrôle ne peut **pas**
voir :

- une ligne rattachée au mauvais programme ou à la mauvaise région, qui laisse les totaux
  justes (erreur réellement commise pendant la transcription : des lignes FEDER accrochées
  au programme de développement rural imprimé juste au-dessus) ;
- les règles de rapprochement, qui ne sont écrites dans aucun total : l'IEJ compté double,
  la contrepartie FSE défalquée, REACT-EU FEDER séparé quand REACT-EU FSE est fondu.

**Les valeurs attendues sont un relevé indépendant, saisi à la main depuis les PDF**, et
non dérivées des tables testées : un test qui lit sa réponse dans ce qu'il contrôle ne
peut pas voir une transcription fausse (constaté deux fois sur ce dépôt, cf. CLAUDE.md).
"""

import pytest
from programme_totals_2014_2020 import CLE_NATIONAL, calculer, contrepartie_fse

from reference.programmes_2014_2020 import (
    ALLOCATION_SPECIFIQUE_IEJ,
    CONTREPARTIE_FSE_IEJ,
    DOTATIONS,
    PROGRAMMES,
    dotation_iej_totale,
    programme,
)
from reference.react_eu_2014_2020 import MAQUETTES

# --- Relevés indépendants ---------------------------------------------------------

# Rattachement CCI -> région moderne, relevé sur la colonne "Région" de la table 1.6 de
# l'Accord (p.165-173) puis converti en région post-2016. Volontairement partiel : les
# cas qui portent un risque réel — anciennes régions fusionnées, DROM-COM, programmes
# d'État distincts du programme du Conseil régional sur le même territoire.
REGIONS_ATTENDUES = {
    "2014FR16M0OP002": "Auvergne-Rhône-Alpes",   # ex-Auvergne
    "2014FR16M2OP010": "Auvergne-Rhône-Alpes",   # ex-Rhône-Alpes
    "2014FR16M0OP014": "Bourgogne-Franche-Comté",  # ex-Bourgogne
    "2014FR16M2OP005": "Bourgogne-Franche-Comté",  # ex-Franche-Comté
    "2014FR16M0OP001": "Nouvelle-Aquitaine",     # ex-Aquitaine
    "2014FR16M2OP006": "Nouvelle-Aquitaine",     # ex-Limousin
    "2014FR16M2OP009": "Nouvelle-Aquitaine",     # ex-Poitou-Charentes
    "2014FR16M2OP001": "Normandie",              # ex-Basse-Normandie
    "2014FR16M0OP005": "Normandie",              # ex-Haute-Normandie
    "2014FR16M0OP004": "Grand Est",              # ex-Champagne-Ardenne
    "2014FR16M0OP015": "Grand Est",              # ex-Lorraine
    "2014FR16RFOP006": "Grand Est",              # PO FEDER Alsace
    "2014FR05M9OP002": "Grand Est",              # PO FSE Alsace
    "2014FR16M0OP008": "Hauts-de-France",        # ex-Picardie
    "2014FR16M0OP012": "Hauts-de-France",        # ex-Nord-Pas-de-Calais
    "2014FR16M0OP006": "Occitanie",              # ex-Languedoc-Roussillon
    "2014FR16M0OP007": "Occitanie",              # ex-Midi-Pyrénées
    "2014FR16M0OP009": "Guadeloupe",             # Conseil régional
    "2014FR05M2OP001": "Guadeloupe",             # Guadeloupe et Saint-Martin, État
    "2014FR16M0OP011": "Martinique",             # Conseil régional
    "2014FR05SFOP004": "Martinique",             # PO FSE État
    "2014FR16RFOP007": "La Réunion",             # Conseil régional
    "2014FR05SFOP005": "La Réunion",             # PO FSE État
    "2014FR16M2OP011": "Guyane",                 # Conseil régional
    "2014FR05SFOP003": "Guyane",                 # PO FSE État
    "2014FR16M2OP012": "Mayotte",
    "2014FR16M2OP004": "Corse",
    "2014FR16M2OP003": "Bretagne",
    "2014FR16M2OP008": "Pays de la Loire",
    "2014FR16M0OP003": "Centre-Val de Loire",
    "2014FR16M0OP013": "Provence-Alpes-Côte d'Azur",
    "2014FR05M0OP001": "Île-de-France",
}

# Programmes sans région unique : nationaux et interrégionaux.
CCI_SANS_REGION = {
    "2014FR05SFOP001",  # PO National FSE Emploi et Inclusion
    "2014FR05M9OP001",  # PO National IEJ
    "2014FR16M2TA001",  # PNAT Europ'Act
    "2014FR16RFOP001",  # POI Alpes
    "2014FR16RFOP002",  # POI Loire
    "2014FR16RFOP003",  # POI Massif Central
    "2014FR16RFOP004",  # POI Pyrénées
    "2014FR16RFOP005",  # POI Rhône Saône
}

# Montants relevés ligne à ligne sur la table 1.6 (colonne "Total").
DOTATIONS_ATTENDUES = {
    ("2014FR16M0OP002", "FEDER"): 215_442_139,
    ("2014FR16M0OP002", "FSE"): 34_467_861,
    ("2014FR16M0OP002", "IEJ"): 6_069_483,
    ("2014FR16M2OP010", "FEDER"): 364_091_269,
    ("2014FR16M2OP003", "FEDER"): 307_307_301,
    ("2014FR16M2OP003", "FSE"): 62_192_699,
    ("2014FR16RFOP007", "FEDER"): 1_130_456_061,
    ("2014FR05SFOP001", "FSE"): 2_820_495_562,
    ("2014FR16M2TA001", "FEDER"): 40_829_592,
    ("2014FR16M2TA001", "FSE"): 31_771_039,
    ("2014FR05M9OP001", "IEJ"): 329_418_831,
    ("2014FR16RFOP004", "FEDER"): 24_872_998,
}

# Montants relevés sur la colonne "Maquette UE" des deux tableaux du rapport ANCT.
MAQUETTES_ATTENDUES = {
    ("2014FR16RFOP007", "FEDER"): 340_948_106,
    ("2014FR16M0OP009", "FEDER"): 170_169_923,
    ("2014FR16M0OP012", "FEDER"): 177_879_806,
    ("2014FR16RFOP002", "FEDER"): 7_822_019,
    ("2014FR05SFOP001", "FSE"): 800_060_179,
    ("2014FR05SFOP005", "FSE"): 148_094_472,
    ("2014FR16M0OP009", "FSE"): 9_000_000,
}

# Montants relevés sur la colonne "Montant justifié après le dernier appel de fonds au
# 24 septembre 2024" des mêmes tableaux — arrondis à l'euro comme dans le module (#96).
MONTANTS_JUSTIFIES_ATTENDUES = {
    ("2014FR16M0OP008", "FEDER"): 102_275_167,  # 115 % de la maquette
    ("2014FR16RFOP007", "FEDER"): 251_236_518,  # 73,7 %
    ("2014FR16M0OP011", "FEDER"): 31_544_730,  # 19,8 %, le plus bas du volet FEDER
    ("2014FR05SFOP001", "FSE"): 894_847_747,  # 111,85 %
    ("2014FR05M2OP001", "FSE"): 0,  # aucune dépense certifiée à cette date
    ("2014FR16M0OP009", "FSE"): 0,  # idem, second des deux programmes à 0 %
}


# --- Transcription ----------------------------------------------------------------


@pytest.mark.parametrize("cci,region", sorted(REGIONS_ATTENDUES.items()))
def test_programme_rattache_a_sa_region_moderne(cci, region):
    assert programme(cci).region == region


@pytest.mark.parametrize("cci", sorted(CCI_SANS_REGION))
def test_programme_national_ou_interregional_sans_region(cci):
    assert programme(cci).region is None


def test_programme_leve_sur_un_cci_inconnu():
    # Un CCI absent est une source nouvelle ou une faute de frappe, pas un trou : il doit
    # lever plutôt que renvoyer None et se propager en silence dans un dénominateur.
    with pytest.raises(KeyError):
        programme("2014FR16M0OP999")


@pytest.mark.parametrize("cle,montant", sorted(DOTATIONS_ATTENDUES.items()))
def test_dotation_transcrite_conforme_au_releve(cle, montant):
    cci, fonds = cle
    lignes = [d for d in DOTATIONS if d.cci == cci and d.fonds == fonds]
    assert len(lignes) == 1
    assert lignes[0].montant_ue == montant


@pytest.mark.parametrize("cle,montant", sorted(MAQUETTES_ATTENDUES.items()))
def test_maquette_react_eu_conforme_au_releve(cle, montant):
    cci, fonds = cle
    lignes = [m for m in MAQUETTES if m.cci == cci and m.fonds == fonds]
    assert len(lignes) == 1
    assert lignes[0].montant_ue == montant


@pytest.mark.parametrize("cle,montant", sorted(MONTANTS_JUSTIFIES_ATTENDUES.items()))
def test_montant_justifie_conforme_au_releve(cle, montant):
    cci, fonds = cle
    lignes = [m for m in MAQUETTES if m.cci == cci and m.fonds == fonds]
    assert len(lignes) == 1
    assert lignes[0].montant_justifie == montant


def test_aucun_programme_de_developpement_rural_dans_les_dotations():
    # Les CCI en "06RDR" sont les PDR (FEADER), hors périmètre. Leur présence signalerait
    # le retour de l'erreur d'affectation vue à la transcription — invisible aux totaux.
    intrus = sorted({d.cci for d in DOTATIONS if "06RD" in d.cci or "14MF" in d.cci})
    assert intrus == []


def test_fonds_transcrits_limites_aux_trois_fonds_utiles():
    assert {d.fonds for d in DOTATIONS} == {"FEDER", "FSE", "IEJ"}


def test_chaque_dotation_se_ventile_sur_sept_annees():
    for d in DOTATIONS:
        assert len(d.ventilation) == 7
        assert sum(d.ventilation) == d.montant_ue


# --- Règle de l'IEJ ---------------------------------------------------------------


def test_ressource_iej_vaut_environ_le_double_de_l_allocation_specifique():
    # Accord §1.4.2 : allocation spécifique 471 474 337 €, contrepartie FSE 473 185 393 €.
    cci = "2014FR16M0OP002"  # PO Auvergne, allocation spécifique 6 069 483 €
    assert dotation_iej_totale(cci) == 6_069_483 + contrepartie_fse(6_069_483)
    assert dotation_iej_totale(cci) == pytest.approx(2 * 6_069_483, rel=0.01)


def test_programme_sans_iej_ne_recoit_pas_de_contrepartie():
    assert dotation_iej_totale("2014FR16M2OP003") == 0  # Bretagne : pas de ligne IEJ


def test_contrepartie_repartie_redonne_le_total_national():
    reparti = sum(contrepartie_fse(d.montant_ue) for d in DOTATIONS if d.fonds == "IEJ")
    # Un euro d'écart d'arrondi sur 473 M€ : la répartition au prorata est exacte.
    assert abs(reparti - CONTREPARTIE_FSE_IEJ) <= 1


def test_somme_des_allocations_specifiques_egale_le_total_publie():
    total = sum(d.montant_ue for d in DOTATIONS if d.fonds == "IEJ")
    assert total == ALLOCATION_SPECIFIQUE_IEJ


# --- Agrégation par région --------------------------------------------------------


def test_contrepartie_fse_retranchee_du_fse_de_la_meme_region():
    totaux, detail = calculer()
    for region, part in detail["contrepartie_fse_iej"].items():
        fse_accord = sum(
            d.montant_ue for d in DOTATIONS
            if d.fonds == "FSE" and (programme(d.cci).region or CLE_NATIONAL) == region
        )
        react_fse = sum(
            m.montant_ue for m in MAQUETTES
            if m.fonds == "FSE" and (programme(m.cci).region or CLE_NATIONAL) == region
        )
        assert totaux[region]["FSE"] == fse_accord - part + react_fse


def test_enveloppe_iej_regionale_compte_les_deux_moities():
    # Sans le doublement, le taux de consommation IEJ sort à ~200 % : c'est le symptôme
    # qui a fait découvrir la règle (203 % en Nouvelle-Aquitaine, 229 % sur le PO national).
    totaux, _ = calculer()
    # Auvergne-Rhône-Alpes : allocations spécifiques 6 069 483 (Auvergne) + 0 (Rhône-Alpes).
    specifique = 6_069_483
    assert totaux["Auvergne-Rhône-Alpes"]["IEJ"] == specifique + contrepartie_fse(specifique)


def test_react_eu_feder_reste_un_fonds_distinct():
    # Les données portent un libellé `FEDER REACT-EU` : sa maquette ne doit jamais être
    # fondue dans l'enveloppe FEDER, sinon le taux FEDER est écrasé et le REACT-EU nul.
    totaux, detail = calculer()
    assert totaux["Bretagne"]["FEDER"] == 307_307_301
    assert totaux["Bretagne"]["FEDER REACT-EU"] == 92_779_237
    assert detail["react_eu"]["Bretagne"] == {"FEDER REACT-EU": 92_779_237}


def test_react_eu_justifie_agrege_par_region_hors_totaux():
    # Bretagne n'a qu'un programme REACT-EU FEDER : le justifié s'agrège comme la maquette,
    # mais ne doit jamais entrer dans `totaux` — c'est un taux de référence (#96), pas une
    # enveloppe supplémentaire à additionner au dénominateur du taux de consommation.
    totaux, detail = calculer()
    assert detail["react_eu_justifie"]["Bretagne"] == {"FEDER REACT-EU": 101_127_972}
    assert totaux["Bretagne"]["FEDER REACT-EU"] == 92_779_237


def test_react_eu_fse_est_fondu_dans_le_fse():
    # Aucun libellé ne l'isole dans les données (#82) : le laisser dehors amputerait le
    # dénominateur FSE de 1 215,7 M€ que le numérateur, lui, contient.
    totaux, _ = calculer()
    # Pays de la Loire : FSE Accord 76 711 272, aucune ligne IEJ, maquette FSE 19 000 000.
    assert totaux["Pays de la Loire"]["FSE"] == 76_711_272 + 19_000_000
    assert "FSE REACT-EU" not in totaux["Pays de la Loire"]


def test_fonds_sans_enveloppe_absents_de_la_sortie():
    # FEAD (hors enveloppe structurelle, art. 94) et FEDER-FSE (libellé de données du
    # PNAT Europ'Act, pas un fonds) : absents, jamais à zéro — un zéro se lirait comme
    # une enveloppe épuisée là où il n'y a pas d'enveloppe du tout.
    totaux, _ = calculer()
    for fonds_totaux in totaux.values():
        assert "FEAD" not in fonds_totaux
        assert "FEDER-FSE" not in fonds_totaux


def test_programmes_nationaux_et_interregionaux_agreges_sous_national():
    totaux, _ = calculer()
    assert CLE_NATIONAL in totaux
    # Les 5 POI n'ont que du FEDER ; seul le POI Loire a une maquette REACT-EU.
    assert totaux[CLE_NATIONAL]["FEDER REACT-EU"] == 7_822_019


def test_aucun_montant_negatif():
    # La contrepartie FSE est soustraite : une erreur de répartition la rendrait
    # supérieure au FSE de la région et produirait un dénominateur négatif.
    totaux, _ = calculer()
    for region, fonds_totaux in totaux.items():
        for fonds, montant in fonds_totaux.items():
            assert montant > 0, f"{region}/{fonds} = {montant}"


def test_toutes_les_regions_du_perimetre_metropolitain_et_drom_sont_couvertes():
    totaux, _ = calculer()
    attendues = {p.region for p in PROGRAMMES if p.region}
    assert set(totaux) == attendues | {CLE_NATIONAL}
    assert len(attendues) == 18
