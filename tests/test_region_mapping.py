"""Harmonisation des régions — la brique dont dépend tout agrégat régional.

Une région mal harmonisée ne casse rien : elle déplace des montants d'une région
à l'autre, ou fait disparaître une opération d'un agrégat. Le dashboard affiche
alors des chiffres plausibles et faux.
"""

import pytest
from region_mapping import (
    PROGRAMME_TO_REGION_2014_2020,
    get_unresolved,
    harmonize_region,
    indexer_programmes,
    reset_unresolved,
)


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


# --- 2014-2020 : la période où le rattachement par programme porte l'essentiel ---
#
# Fragments repris **tels quels** du fichier Synergie 14-20, pas inventés : sa
# colonne région n'est remplie qu'à 16,4 %, et les 83,6 % restants ne sont
# rattachés que par le libellé du programme (issue #12).

INDEX_2014_2020 = indexer_programmes(PROGRAMME_TO_REGION_2014_2020)


@pytest.mark.parametrize(
    ("fragment", "attendu"),
    [
        ("91/Languedoc-Roussillon", "Occitanie"),
        ("74/Limousin", "Nouvelle-Aquitaine"),
        ("23/Haute-Normandie", "Normandie"),
        ("25/Basse-Normandie", "Normandie"),
        ("54/Poitou-Charentes", "Nouvelle-Aquitaine"),
        ("72/Aquitaine", "Nouvelle-Aquitaine"),
    ],
)
def test_les_codes_2014_2020_sont_resolus_par_le_code(fragment, attendu):
    """Ces six codes pré-2016 n'existent que dans le fichier 14-20. Ils étaient
    résolus par le repli sur le nom ; ils le sont désormais par le code, comme
    les autres — chacun confirmé par la donnée, où il n'apparaît qu'associé à un
    seul nom.

    Le nom est **remplacé par un intrus** : avec le vrai nom, le repli résout
    aussi bien et le test resterait vert en retirant le code de la table (vu par
    mutation). Seul un nom que rien ne reconnaît prouve que c'est le code qui a
    répondu."""
    code = fragment.split("/", 1)[0]
    regions, _, _ = harmonize_region(f"{code}/Nom absent de toute table", None)

    assert regions == [attendu]
    assert get_unresolved() == [], "le code seul doit suffire, sans repli sur le nom"


@pytest.mark.parametrize(
    ("fragment", "attendu"),
    [
        ("91/Languedoc-Roussillon", "Occitanie"),
        ("74/Limousin", "Nouvelle-Aquitaine"),
        ("23/Haute-Normandie", "Normandie"),
        ("25/Basse-Normandie", "Normandie"),
        ("54/Poitou-Charentes", "Nouvelle-Aquitaine"),
        ("72/Aquitaine", "Nouvelle-Aquitaine"),
    ],
)
def test_les_fragments_2014_2020_reels_donnent_la_bonne_region(fragment, attendu):
    """Les mêmes fragments, tels qu'écrits dans le fichier : code et nom doivent
    dire la même chose, sinon l'un des deux est faux."""
    regions, _, _ = harmonize_region(fragment, None)

    assert regions == [attendu]
    assert get_unresolved() == []


def test_les_96_valeurs_region_2014_2020_sont_toutes_resolues():
    """Échantillon des formes réellement présentes, dont les multi-régions
    séparées par `|`. Un fragment non résolu passe quand même (repli sur le nom
    brut) : c'est `UNRESOLVED_FRAGMENTS` qui le dit, et personne d'autre."""
    for valeur in [
        "91/Languedoc-Roussillon",
        "82/Rhône-Alpes | 83/Auvergne",
        "26/Bourgogne | 43/Franche-Comté",
        "72/Aquitaine | 54/Poitou-Charentes | 74/Limousin",
        "23/Haute-Normandie | 25/Basse-Normandie",
    ]:
        harmonize_region(valeur, None)

    assert get_unresolved() == []


def test_deux_anciennes_regions_fusionnees_ne_font_pas_une_interregionale():
    """Aquitaine, Poitou-Charentes et Limousin sont **une** région depuis 2016 :
    les compter comme interrégionales sortirait l'opération des agrégats de
    Nouvelle-Aquitaine pour la ranger dans un « à cheval » qui n'existe plus."""
    regions, interregional, _ = harmonize_region(
        "72/Aquitaine | 54/Poitou-Charentes | 74/Limousin", None
    )

    assert regions == ["Nouvelle-Aquitaine"]
    assert not interregional


def test_un_programme_2014_2020_rattache_l_operation_a_sa_region():
    """Le cas majoritaire de la période : région absente, programme connu."""
    regions, _, national = harmonize_region(
        None,
        "Programme Opérationnel FEDER-FSE Languedoc-Roussillon 2014-2020",
        INDEX_2014_2020,
    )

    assert regions == ["Occitanie"]
    assert not national


def test_sans_index_de_periode_un_programme_2014_2020_reste_national():
    """Le paramètre n'est pas cosmétique : oublier de passer l'index de la
    période rattacherait 20 821 opérations 14-20 au Volet national sans lever la
    moindre erreur."""
    regions, _, national = harmonize_region(
        None, "Programme Opérationnel FEDER-FSE Languedoc-Roussillon 2014-2020"
    )

    assert regions == []
    assert national


def test_un_programme_interregional_2014_2020_reste_au_volet_national():
    """Choix de v1 (issue #12, étape C4) : les 5 programmes interrégionaux valent
    `None` dans la table, faute de la liste des régions de chaque massif. Ils
    sont comptés à part, pas répartis au jugé."""
    regions, interregional, national = harmonize_region(
        None, "Programme opérationnel Interrégional FEDER Pyrénées 2014-2020", INDEX_2014_2020
    )

    assert regions == []
    assert not interregional
    assert national


def test_un_programme_national_2014_2020_reste_national():
    regions, _, national = harmonize_region(
        None, "Programme opérationnel FEAD 2014-2020", INDEX_2014_2020
    )

    assert regions == []
    assert national


def test_les_deux_periodes_ne_se_rattachent_pas_l_une_a_l_autre():
    """Chaque index ne connaît que ses programmes : un libellé 21-27 passé avec
    l'index 14-20 (ou l'inverse) doit rester non rattaché, pas retomber sur une
    région approchante."""
    regions, _, national = harmonize_region(
        None, "Programme Corse FEDER-FSE+ 2021-2027", INDEX_2014_2020
    )

    assert regions == []
    assert national
