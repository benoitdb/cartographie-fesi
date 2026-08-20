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
