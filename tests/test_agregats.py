"""Agrégats du pipeline : les totaux que le dashboard affiche sans les recalculer.

`data.json` porte un bloc `aggregates` que les pages lisent tel quel — le total
d'une région, d'un fonds, d'un objectif stratégique. Une erreur ici ne provoque
aucune exception : elle produit un chiffre faux, affiché avec le même aplomb
qu'un chiffre juste.

Jusqu'à l'extraction d'`agregats.py` (issue #60), ce calcul n'était vérifiable
qu'en régénérant les 45 Mo du fichier complet, donc seulement sur un poste
disposant du XLSX source. Ici, tout tourne sur des DataFrames construits à la
main, y compris en CI.

L'invariant central est le découpage : une opération compte dans **une seule**
partition géographique, mais dans **tous** les agrégats non géographiques.
"""

import json

import pandas as pd
import pytest
from agregats import calculer_agregats, partitionner

COLS = {
    "numero_op": "Numéro Opération",
    "fonds": "Fonds",
    "objectif_strat": "Objectif stratégique",
    "montant_ue": "Montant UE",
    "depenses": "Total des dépenses éligibles",
}


def operation(
    numero,
    regions=("Occitanie",),
    montant=100.0,
    depenses=200.0,
    fonds="FEDER",
    objectif="OS1 — Europe plus compétitive",
    interregional=False,
    national=False,
):
    return {
        "Numéro Opération": numero,
        "Fonds": fonds,
        "Objectif stratégique": objectif,
        "Montant UE": montant,
        "Total des dépenses éligibles": depenses,
        "regions_modernes": list(regions),
        "is_interregional": interregional,
        "is_national": national,
    }


def df_operations(*ops):
    return pd.DataFrame(list(ops))


# --- Partitions ----------------------------------------------------------------


def test_les_trois_partitions_sont_disjointes_et_couvrent_tout():
    df = df_operations(
        operation("mono"),
        operation("inter", regions=("Occitanie", "Bretagne"), interregional=True),
        operation("nat", regions=(), national=True),
    )
    partitions = partitionner(df)

    assert partitions.mono_region["Numéro Opération"].tolist() == ["mono"]
    assert partitions.interregional["Numéro Opération"].tolist() == ["inter"]
    assert partitions.national["Numéro Opération"].tolist() == ["nat"]
    assert sum(len(p) for p in partitions) == len(df)


# --- Découpage géographique vs non géographique --------------------------------


def test_une_operation_interregionale_n_est_comptee_dans_aucune_region():
    """Sinon elle serait comptée dans chacune de ses régions, et la somme des
    régions dépasserait le montant total."""
    df = df_operations(
        operation("mono", montant=100.0),
        operation("inter", regions=("Occitanie", "Bretagne"), montant=50.0, interregional=True),
    )
    agregats = calculer_agregats(df, COLS)

    assert agregats["by_region"]["Occitanie"]["count"] == 1
    assert agregats["by_region"]["Occitanie"]["montant_ue_total"] == 100.0
    assert "Bretagne" not in agregats["by_region"]
    assert agregats["interregional"]["montant_ue_total"] == 50.0


def test_le_volet_national_est_a_part_des_regions():
    df = df_operations(
        operation("mono", montant=100.0),
        operation("nat", regions=(), montant=700.0, national=True),
    )
    agregats = calculer_agregats(df, COLS)

    assert agregats["by_region"]["Occitanie"]["montant_ue_total"] == 100.0
    assert agregats["national"]["montant_ue_total"] == 700.0


def test_les_agregats_par_fonds_portent_sur_toutes_les_operations():
    """Y compris le volet national et l'interrégional : la dimension « fonds »
    n'est pas géographique. Les exclure creuserait un écart inexpliqué entre la
    somme par fonds et le montant total."""
    df = df_operations(
        operation("mono", montant=100.0),
        operation("inter", regions=("Occitanie", "Bretagne"), montant=50.0, interregional=True),
        operation("nat", regions=(), montant=700.0, national=True),
    )
    agregats = calculer_agregats(df, COLS)

    assert agregats["by_fonds"]["FEDER"]["count"] == 3
    assert agregats["by_fonds"]["FEDER"]["montant_ue_total"] == 850.0
    assert agregats["by_objectif_strategique"]["OS1 — Europe plus compétitive"]["count"] == 3


def test_la_somme_des_fonds_egale_le_montant_total_du_perimetre():
    df = df_operations(
        operation("a", fonds="FEDER", montant=100.0),
        operation("b", fonds="FSE+", montant=30.0),
        operation("c", fonds="FTJ", montant=70.0, regions=(), national=True),
    )
    agregats = calculer_agregats(df, COLS)

    total_par_fonds = sum(v["montant_ue_total"] for v in agregats["by_fonds"].values())
    assert total_par_fonds == pytest.approx(df["Montant UE"].sum())


def test_une_operation_mono_region_sans_region_resolue_n_apparait_dans_aucune_region():
    """Cas réel : l'harmonisation n'a pas résolu la région, l'opération n'est pour
    autant ni interrégionale ni nationale. Elle compte dans les totaux par fonds,
    mais la somme des régions est alors inférieure au total — comportement
    volontaire, à connaître avant de conclure à un écart de calcul."""
    df = df_operations(
        operation("resolue", montant=100.0),
        operation("orpheline", regions=(), montant=40.0),
    )
    agregats = calculer_agregats(df, COLS)

    assert list(agregats["by_region"]) == ["Occitanie"]
    assert agregats["by_region"]["Occitanie"]["montant_ue_total"] == 100.0
    assert agregats["by_fonds"]["FEDER"]["montant_ue_total"] == 140.0


# --- Contenu des résumés -------------------------------------------------------


def test_un_resume_porte_montants_totaux_moyens_et_depenses():
    df = df_operations(
        operation("a", montant=100.0, depenses=400.0),
        operation("b", montant=300.0, depenses=600.0),
    )
    resume = calculer_agregats(df, COLS)["by_region"]["Occitanie"]

    assert resume == {
        "count": 2,
        "montant_ue_total": 400.0,
        "montant_ue_moyen": 200.0,
        "depenses_total": 1000.0,
        "depenses_moyen": 500.0,
    }


def test_l_agregat_interregional_liste_les_numeros_d_operation():
    """Ces opérations n'apparaissent dans aucune région : sans cette liste, rien
    ne permettrait de les retrouver depuis le dashboard."""
    df = df_operations(
        operation("A1", regions=("Occitanie", "Bretagne"), interregional=True),
        operation("A2", regions=("Corse", "Bretagne"), interregional=True),
    )
    agregats = calculer_agregats(df, COLS)

    assert agregats["interregional"]["operations"] == ["A1", "A2"]


def test_les_montants_sont_des_flottants_python_serialisables():
    """`.sum()` rend un `numpy.float64`, que `json.dump` refuse."""
    df = df_operations(operation("a"))
    assert type(calculer_agregats(df, COLS)["by_region"]["Occitanie"]["montant_ue_total"]) is float


# --- Croisements ---------------------------------------------------------------


def test_les_croisements_sont_indexes_par_cle_composee():
    df = df_operations(
        operation("a", fonds="FEDER", montant=100.0),
        operation("b", fonds="FSE+", montant=30.0),
    )
    agregats = calculer_agregats(df, COLS)

    assert agregats["by_region_fonds"]["Occitanie|FEDER"] == {
        "region": "Occitanie",
        "fonds": "FEDER",
        "count": 1,
        "montant_ue_total": 100.0,
    }
    assert "Occitanie|FSE+" in agregats["by_region_fonds"]


def test_un_croisement_sans_operation_est_absent_plutot_qu_a_zero():
    """Le dashboard itère sur ces clés : une ligne à zéro par couple possible
    ferait apparaître des régions sans projet dans les graphes croisés."""
    df = df_operations(
        operation("a", regions=("Occitanie",), fonds="FEDER"),
        operation("b", regions=("Bretagne",), fonds="FSE+"),
    )
    croisements = calculer_agregats(df, COLS)["by_region_fonds"]

    assert set(croisements) == {"Occitanie|FEDER", "Bretagne|FSE+"}


def test_les_croisements_region_ne_portent_que_sur_le_mono_region():
    df = df_operations(
        operation("mono", montant=100.0),
        operation("nat", regions=(), montant=700.0, national=True),
    )
    croisements = calculer_agregats(df, COLS)["by_region_fonds"]

    assert sum(v["montant_ue_total"] for v in croisements.values()) == 100.0


def test_le_croisement_fonds_objectif_porte_sur_toutes_les_operations():
    df = df_operations(
        operation("mono", fonds="FEDER", montant=100.0),
        operation("nat", regions=(), fonds="FEDER", montant=700.0, national=True),
    )
    croisements = calculer_agregats(df, COLS)["by_fonds_objectif"]

    assert croisements["FEDER|OS1 — Europe plus compétitive"]["montant_ue_total"] == 800.0


# --- Partitions ou catégories vides --------------------------------------------


def test_une_partition_vide_est_absente_du_resultat():
    """Comportement historique conservé : le dashboard lit `aggregates["national"]`
    sans valeur par défaut. C'est aussi la contrainte à respecter en construisant
    un échantillon de test — les trois partitions doivent y être représentées."""
    agregats = calculer_agregats(df_operations(operation("mono")), COLS)

    assert "national" not in agregats
    assert "interregional" not in agregats
    assert agregats["by_region"]


def test_un_objectif_strategique_manquant_n_ouvre_pas_de_categorie():
    """L'opération reste comptée par fonds : c'est l'objectif qui est inconnu,
    pas l'opération."""
    df = df_operations(
        operation("a", objectif="OS1 — Europe plus compétitive", montant=100.0),
        operation("b", objectif=None, montant=40.0),
    )
    agregats = calculer_agregats(df, COLS)

    assert list(agregats["by_objectif_strategique"]) == ["OS1 — Europe plus compétitive"]
    assert agregats["by_fonds"]["FEDER"]["montant_ue_total"] == 140.0


def test_les_categories_sont_triees_pour_une_sortie_reproductible():
    """Deux régénérations du pipeline sur la même source doivent produire le même
    fichier au bit près — c'est la vérification de non-régression utilisée à
    chaque changement de pipeline."""
    df = df_operations(
        operation("a", regions=("Occitanie",), fonds="FSE+"),
        operation("b", regions=("Bretagne",), fonds="FEDER"),
    )
    agregats = calculer_agregats(df, COLS)

    assert list(agregats["by_region"]) == ["Bretagne", "Occitanie"]
    assert list(agregats["by_fonds"]) == ["FEDER", "FSE+"]


# --- Période sans dimension thématique (2014-2020) -----------------------------
#
# Le fichier Synergie 14-20 n'a pas d'objectif stratégique : sa dimension
# thématique est le `Domaine d'intervention`, vide à 100 % (issues #12, #73).
# `cols` n'y porte donc pas la clé `objectif_strat`.

COLS_SANS_OBJECTIF = {cle: valeur for cle, valeur in COLS.items() if cle != "objectif_strat"}

BLOCS_OBJECTIF = {"by_objectif_strategique", "by_region_objectif", "by_fonds_objectif"}


def df_sans_objectif(*ops):
    """Les mêmes opérations, sans la colonne d'objectif stratégique — comme le
    DataFrame que produit la lecture du fichier 14-20."""
    return df_operations(*ops).drop(columns=["Objectif stratégique"])


def test_sans_dimension_thematique_les_blocs_objectif_sont_absents():
    """Absents, pas vides : une clé présente à `{}` se lit comme « dimension
    mesurée, aucune valeur », alors qu'elle n'existe pas dans la source."""
    agregats = calculer_agregats(
        df_sans_objectif(
            operation("A", montant=100.0),
            operation("B", regions=("Corse",), montant=50.0),
            operation("C", national=True, montant=10.0),
        ),
        COLS_SANS_OBJECTIF,
    )

    assert BLOCS_OBJECTIF.isdisjoint(agregats)


def test_sans_dimension_thematique_les_autres_agregats_restent_complets():
    """Le reste du calcul ne doit pas être amputé au passage : c'est tout ce que
    le dashboard peut afficher pour cette période."""
    agregats = calculer_agregats(
        df_sans_objectif(
            operation("A", montant=100.0),
            operation("B", regions=("Corse",), fonds="FSE", montant=50.0),
            operation("C", regions=("Corse", "Occitanie"), interregional=True, montant=7.0),
            operation("D", national=True, montant=10.0),
        ),
        COLS_SANS_OBJECTIF,
    )

    assert set(agregats) == {"by_region", "national", "interregional", "by_fonds", "by_region_fonds"}
    assert agregats["by_region"]["Occitanie"]["montant_ue_total"] == 100.0
    assert agregats["by_fonds"]["FSE"]["montant_ue_total"] == 50.0
    assert agregats["by_region_fonds"]["Corse|FSE"]["montant_ue_total"] == 50.0
    assert agregats["national"]["montant_ue_total"] == 10.0
    assert agregats["interregional"]["montant_ue_total"] == 7.0


def test_aucune_categorie_thematique_n_est_inventee():
    """Le piège serait de remplir la dimension d'un « Non spécifié » pour garder
    la même forme de sortie entre périodes : ce serait une catégorie qui n'existe
    dans aucune source, affichée comme si elle avait été mesurée."""
    agregats = calculer_agregats(
        df_sans_objectif(operation("A"), operation("B", national=True)),
        COLS_SANS_OBJECTIF,
    )

    assert "Non spécifié" not in json.dumps(agregats, ensure_ascii=False)


def test_avec_dimension_thematique_les_blocs_objectif_sont_toujours_la():
    """Garde-fou de non-régression : rendre les blocs conditionnels ne doit rien
    retirer à la période qui porte la dimension."""
    agregats = calculer_agregats(
        df_operations(
            operation("A", objectif="OS1"),
            operation("B", regions=("Corse",), objectif="OS2"),
        ),
        COLS,
    )

    assert BLOCS_OBJECTIF <= set(agregats)
    assert set(agregats["by_objectif_strategique"]) == {"OS1", "OS2"}
