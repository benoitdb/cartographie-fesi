"""Pilotage : taux de consommation, reste à engager, trajectoire.

Ce module compare des montants *programmés* (Accord de partenariat) à des
montants *engagés* (opérations réelles). Deux règles y ont été établies après
coup, à la suite d'un chiffre faux constaté à l'écran, et doivent le rester :

- le reste à engager agrégé est la somme des restes **par fonds**, chacun
  plancher à zéro — un fonds en dépassement ne doit pas absorber le reliquat
  d'un autre (cas constaté : Auvergne-Rhône-Alpes, ~150 M€ de FEDER restants
  masqués par le dépassement FSE+) ;
- un dépassement s'affiche (rouge, ⚠️) plutôt que de se faire tronquer à 100%.

`render_kpi_pilotage` étant une fonction de rendu, on l'éprouve via `AppTest`
sur les valeurs effectivement écrites, pas sur un calcul intermédiaire.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

pytest.importorskip("streamlit", reason="dépendances du dashboard non installées")

from streamlit.testing.v1 import AppTest  # noqa: E402

from utils.pilotage import (  # noqa: E402
    PERIODE_DEBUT,
    PERIODE_FIN,
    build_fonds_mini_bar,
    build_ranking_programme_vs_engage,
    build_trajectoire,
)

# --- Bloc KPI : le reste à engager agrégé --------------------------------------


def _script_kpi_avec_depassement():
    """Script rendu par AppTest : FEDER à 80% (200 M€ restants) et FSE+ en
    dépassement de 50 M€."""
    import pandas as pd

    from utils.pilotage import render_kpi_pilotage

    df = pd.DataFrame(
        {
            "fonds": ["FEDER", "FSE+"],
            "programme": [1_000e6, 100e6],
            "engage": [800e6, 150e6],
        }
    )
    render_kpi_pilotage(df, df["programme"].sum(), df["engage"].sum())


def test_un_depassement_sur_un_fonds_ne_masque_pas_le_reste_d_un_autre():
    """200 M€ (reste FEDER), pas 150 M€ (1 100 − 950 en agrégé) : la soustraction
    globale ferait disparaître 50 M€ de FEDER encore à engager."""
    at = AppTest.from_function(_script_kpi_avec_depassement, default_timeout=60).run()

    assert not at.exception
    restes = [m.value for m in at.markdown if "Reste à engager" in m.value]
    assert restes == ["**Reste à engager (est.) :** 200.0 M€"]


def test_le_bloc_kpi_signale_le_depassement_et_en_explique_la_cause():
    at = AppTest.from_function(_script_kpi_avec_depassement, default_timeout=60).run()
    captions = [c.value for c in at.caption]

    assert any("150%" in c and "dépassement" in c for c in captions)
    assert any("transfert" in c for c in captions), (
        "le dépassement FSE+ doit rester expliqué comme un transfert national → régional"
    )
    assert any("préliminaires" in c for c in captions), (
        "la réserve méthodologique doit accompagner tout taux de consommation"
    )


def _script_kpi_sans_programmation():
    import pandas as pd

    from utils.pilotage import render_kpi_pilotage

    df = pd.DataFrame({"fonds": ["FTJ"], "programme": [0.0], "engage": [10e6]})
    render_kpi_pilotage(df, 0, 10e6)


def test_sans_montant_programme_le_bloc_kpi_n_affiche_rien():
    """Un périmètre absent du Tableau 9B ne doit pas produire un bloc de
    pilotage à 0 €, qui se lirait comme une enveloppe nulle."""
    at = AppTest.from_function(_script_kpi_sans_programmation, default_timeout=60).run()

    assert not at.exception
    assert not at.markdown


# --- Mini barre de progression par fonds ---------------------------------------


ROUGE_DEPASSEMENT = "#e34948"
BLEU_PAR_DEFAUT = "#4C78A8"


def test_la_mini_barre_affiche_le_taux_consomme():
    barre = build_fonds_mini_bar(engage=750.0, programme=1000.0).data[0]
    assert barre.text == ("75%",)
    assert barre.marker.color == BLEU_PAR_DEFAUT


def test_la_mini_barre_passe_au_rouge_et_depasse_le_repere_en_cas_de_depassement():
    """`st.progress` plafonne à 100% : c'est précisément ce qu'il ne faut pas
    ici, le dépassement doit rester visible."""
    fig = build_fonds_mini_bar(engage=1500.0, programme=1000.0)
    barre = fig.data[0]

    assert barre.text == ("150% ⚠️",)
    assert barre.marker.color == ROUGE_DEPASSEMENT
    assert barre.x == (1500.0,), "la barre porte l'engagé réel, non tronqué au programmé"
    assert fig.layout.xaxis.range[1] >= 1500.0, "l'axe doit laisser voir la partie en dépassement"


def test_le_rouge_de_depassement_prime_sur_la_couleur_de_categorie():
    barre = build_fonds_mini_bar(engage=1500.0, programme=1000.0, color="#1baf7a").data[0]
    assert barre.marker.color == ROUGE_DEPASSEMENT


def test_la_couleur_de_categorie_est_utilisee_hors_depassement():
    barre = build_fonds_mini_bar(engage=500.0, programme=1000.0, color="#1baf7a").data[0]
    assert barre.marker.color == "#1baf7a"


def test_une_enveloppe_nulle_ne_divise_pas_par_zero():
    fig = build_fonds_mini_bar(engage=500.0, programme=0)
    assert fig.data[0].text == ("0%",)
    assert fig.layout.xaxis.range[1] == pytest.approx(575.0)


# --- Classement programmé vs engagé --------------------------------------------


def _df_classement():
    return pd.DataFrame(
        {
            "region": ["Petite", "Grande", "Dépassée"],
            "engage": [50.0, 800.0, 120.0],
            "programme": [100.0, 1000.0, 100.0],
        }
    )


def test_le_classement_est_trie_par_montant_programme_croissant():
    """Tri croissant : Plotly empile les barres horizontales du bas vers le
    haut, le plus gros programmé se retrouve donc en tête à l'affichage."""
    fig = build_ranking_programme_vs_engage(_df_classement(), "region", "engage", "programme")
    assert list(fig.data[0].y) == ["Petite", "Dépassée", "Grande"]


def test_le_classement_etiquette_chaque_ligne_de_son_taux_consomme():
    fig = build_ranking_programme_vs_engage(_df_classement(), "region", "engage", "programme")
    assert list(fig.data[1].text) == ["50%", "120% ⚠️", "80%"]


def test_le_classement_colore_en_rouge_la_seule_ligne_en_depassement():
    fig = build_ranking_programme_vs_engage(_df_classement(), "region", "engage", "programme")
    assert list(fig.data[1].marker.color) == [BLEU_PAR_DEFAUT, ROUGE_DEPASSEMENT, BLEU_PAR_DEFAUT]


def test_la_legende_du_depassement_n_apparait_que_s_il_y_en_a_un():
    sans_depassement = _df_classement().query("region != 'Dépassée'")
    fig = build_ranking_programme_vs_engage(sans_depassement, "region", "engage", "programme")
    assert [trace.name for trace in fig.data] == ["Programmé", "Engagé"]


# --- Trajectoire ---------------------------------------------------------------


def test_la_trajectoire_cumule_les_engagements_dans_l_ordre_des_dates():
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2023-01-01", "2022-01-01", "2022-01-01"],
            "Montant UE": [30.0, 100.0, 20.0],
        }
    )
    reel = build_trajectoire(df, montant_programme=1000.0).data[0]

    # Deux opérations au même jour comptent pour un seul point cumulé.
    assert list(reel.y) == [120.0, 150.0]


def test_le_rythme_lineaire_de_reference_va_de_zero_a_l_enveloppe_sur_la_periode():
    df = pd.DataFrame({"Date de début de l'opération": ["2022-01-01"], "Montant UE": [100.0]})
    reference = build_trajectoire(df, montant_programme=1000.0).data[1]

    assert list(reference.x) == [PERIODE_DEBUT, PERIODE_FIN]
    assert list(reference.y) == [0, 1000.0]


def test_sans_enveloppe_connue_aucun_rythme_de_reference_n_est_trace():
    df = pd.DataFrame({"Date de début de l'opération": ["2022-01-01"], "Montant UE": [100.0]})
    assert len(build_trajectoire(df, montant_programme=0).data) == 1
