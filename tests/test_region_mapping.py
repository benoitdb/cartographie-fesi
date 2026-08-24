"""Harmonisation des régions — la brique dont dépend tout agrégat régional.

Une région mal harmonisée ne casse rien : elle déplace des montants d'une région
à l'autre, ou fait disparaître une opération d'un agrégat. Le dashboard affiche
alors des chiffres plausibles et faux.
"""

import pytest
from region_mapping import get_unresolved, harmonize_region, reset_unresolved


@pytest.fixture(autouse=True)
def _repartir_de_zero():
    """UNRESOLVED_FRAGMENTS est un état global du module : sans remise à zéro,
    un test verrait les fragments non résolus des tests précédents."""
    reset_unresolved()


def test_un_code_ancien_est_traduit_en_region_moderne():
    """Loi NOTRE : le fichier source mélange codes pré et post-2016."""
    regions, interregional, national = harmonize_region("22/Picardie", "peu importe")

    assert regions == ["Hauts-de-France"]
    assert not interregional
    assert not national


def test_une_region_deja_moderne_est_conservee_telle_quelle():
    regions, _, _ = harmonize_region("Bretagne", "peu importe")

    assert regions == ["Bretagne"]


def test_un_code_inconnu_est_resolu_par_son_nom():
    """Le champ source associe toujours un nom à son code : un code jamais
    rencontré ne doit pas faire perdre l'opération, le nom suffit."""
    regions, _, _ = harmonize_region("99/Bretagne", "peu importe")

    assert regions == ["Bretagne"]


def test_un_fragment_non_resolu_est_signale_et_non_avale():
    """Le comportement qui compte : ne pas planter, mais ne pas se taire non
    plus. Un fragment inconnu reste consultable après le passage du pipeline."""
    regions, _, _ = harmonize_region("99/Région Inexistante", "peu importe")

    assert regions == ["Région Inexistante"]
    assert get_unresolved() == ["99/Région Inexistante"]


def test_plusieurs_regions_donnent_une_operation_interregionale():
    regions, interregional, national = harmonize_region(
        "22/Picardie | Bretagne", "peu importe"
    )

    assert regions == ["Bretagne", "Hauts-de-France"]
    assert interregional
    assert not national


def test_deux_ecritures_de_la_meme_region_ne_la_rendent_pas_interregionale():
    """Dédoublonnage après harmonisation : le code ancien et le nom moderne
    d'une même région ne doivent pas faire compter l'opération deux fois."""
    regions, interregional, _ = harmonize_region(
        "22/Picardie | Hauts-de-France", "peu importe"
    )

    assert regions == ["Hauts-de-France"]
    assert not interregional


def test_volet_national_n_est_pas_une_region():
    """Valeur sentinelle du fichier source, pas un territoire."""
    regions, interregional, national = harmonize_region("Volet national", "peu importe")

    assert regions == []
    assert not interregional
    assert national


def test_region_absente_mais_programme_regional_rattache_l_operation():
    regions, _, national = harmonize_region(None, "Programme Corse FEDER-FSE+ 2021-2027")

    assert regions == ["Corse"]
    assert not national


def test_region_absente_et_programme_national_donne_une_operation_nationale():
    """Les programmes nationaux sont volontairement absents de la table de
    rattachement : pas de région à inventer."""
    regions, _, national = harmonize_region(None, "Programme national FSE+ 2021-2027")

    assert regions == []
    assert national


def test_une_region_vide_est_traitee_comme_absente():
    regions, _, national = harmonize_region("", "Programme national FSE+ 2021-2027")

    assert regions == []
    assert national


def test_apostrophe_typographique_du_programme_rattache_quand_meme():
    """Issue #71 : le fichier source écrit PACA avec l'apostrophe typographique
    (U+2019), la table de rattachement avec l'apostrophe droite (U+0027). Comparés
    au caractère près, 287 opérations sans région retombaient sur le Volet
    national — 265 M€ au mauvais endroit.

    Les deux graphies étant indiscernables à l'œil — ce qui a rendu le défaut
    invisible —, le test vérifie explicitement laquelle il emploie."""
    programme_source = (
        "Programme Provence-Alpes-Côte d’Azur et Massif des Alpes FEDER-FSE+-FTJ 2021-2027"
    )
    assert "’" in programme_source

    regions, _, national = harmonize_region(None, programme_source)

    assert regions == ["Provence-Alpes-Côte d'Azur"]
    assert not national


def test_espace_insecable_du_programme_rattache_quand_meme():
    """Même classe de défaut, latente celle-là : le libellé source de Pays de la
    Loire porte une espace insécable là où la table a une espace ordinaire. Ses
    opérations ont toutes leur région renseignée aujourd'hui — le repli se
    réveillerait au premier export où elle serait vide."""
    regions, _, national = harmonize_region(
        None, "Programme Pays de la Loire\xa0 FEDER-FSE+-FTJ 2021-2027"
    )

    assert regions == ["Pays de la Loire"]
    assert not national


def test_le_rattachement_par_programme_ignore_la_casse():
    """Corollaire de la normalisation : ce qui vaut pour les apostrophes et les
    espaces vaut pour la casse, comme pour les libellés de colonnes."""
    regions, _, _ = harmonize_region(None, "programme corse feder-fse+ 2021-2027")

    assert regions == ["Corse"]


def test_un_programme_inconnu_ne_devient_pas_regional_par_normalisation():
    """La normalisation élargit la comparaison, elle ne doit pas rapprocher deux
    programmes distincts : un libellé absent de la table reste national."""
    regions, _, national = harmonize_region(None, "Programme Corse FEDER 2007-2013")

    assert regions == []
    assert national
