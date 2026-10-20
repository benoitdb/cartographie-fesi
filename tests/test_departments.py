"""Rattachement départemental (`data-pipeline/departements.py`, #232) — la cascade dont
dépendent toutes les cartes par département, sur les deux périodes. Calculée par le
pipeline et écrite dans les Parquet ; le dashboard en garde l'affichage
(`dashboard/utils/departments.py`, tableau testé plus bas).

`zone_dept` est la brique qui a motivé l'issue #92 : le champ Zone (Synergie) porte le
lieu réel du projet, validé à 100 % d'accord avec le champ pipeline "Département de
l'opération" sur les données réelles (voir son docstring) — d'où sa priorité sur
l'approximation par code postal du bénéficiaire (siège, pas lieu du projet).
"""

import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))
sys.path.insert(0, str(RACINE / "data-pipeline"))

from departements import (  # noqa: E402
    DEPT_SOURCES,
    ajouter_departements,
    cp_to_dept,
    rattacher_departement,
    zone_dept,
)


def test_zone_dept_segment_dept_simple():
    assert zone_dept("DEPT/075/Paris") == "75"


def test_zone_dept_segment_comm_metropole():
    assert zone_dept("COMM/94028/Créteil") == "94"


def test_zone_dept_segment_comm_dom():
    assert zone_dept("COMM/97411/Saint-Pierre") == "974"


def test_zone_dept_segment_arrdt():
    assert zone_dept("ARRDT/0921/Antony") == "92"


def test_zone_dept_segment_cant():
    assert zone_dept("CANT/07812/Mantes-la-Jolie") == "78"


def test_zone_dept_segment_quar_code_iris():
    assert zone_dept("QUAR/540600000/Belleville") == "54"


def test_zone_dept_resout_corse_via_dept():
    """cp_to_dept ne peut pas trancher 2A/2B : Zone porte l'alpha directement dans le code."""
    assert zone_dept("DEPT/02A/Corse-du-Sud") == "2A"


def test_zone_dept_resout_corse_via_comm():
    assert zone_dept("COMM/2A004/Ajaccio") == "2A"


def test_zone_dept_ignore_reg_et_pays_seuls():
    assert zone_dept("REG/11/Île-de-France|PAYS/1/France entière") is None


def test_zone_dept_plusieurs_segments_qui_saccordent():
    assert zone_dept("REG/11/Île-de-France|DEPT/075/Paris|COMM/75056/Paris") == "75"


def test_zone_dept_segments_en_desaccord_retourne_none():
    assert zone_dept("DEPT/075/Paris|COMM/94028/Créteil") is None


def test_zone_dept_vide_ou_absent():
    assert zone_dept("") is None
    assert zone_dept(None) is None


def test_rattacher_departement_priorite_au_champ_pipeline_sur_zone():
    assert rattacher_departement(departement="42/Loire", zone="DEPT/075/Paris") == ("42", "opération")


def test_rattacher_departement_zone_avant_code_postal():
    assert rattacher_departement(zone="DEPT/075/Paris", cp_beneficiaire="13001") == ("75", "zone")


def test_rattacher_departement_zone_resout_corse_la_ou_le_code_postal_echoue():
    assert cp_to_dept("20000") is None  # le cas que Zone débloque
    assert rattacher_departement(zone="COMM/2A004/Ajaccio", cp_beneficiaire="20000") == ("2A", "zone")


def test_rattacher_departement_repli_sur_code_postal_si_zone_absente():
    assert rattacher_departement(cp_beneficiaire="13001") == ("13", "approximé")


def test_rattacher_departement_repli_sur_nom_si_rien_dautre():
    assert rattacher_departement(nom_benef="Ville de Bastia") == ("2B", "nom du bénéficiaire")


def test_rattacher_departement_inconnu_si_rien_ne_resout():
    assert rattacher_departement() == (None, "inconnu")


def test_dept_sources_contient_zone():
    assert "zone" in DEPT_SOURCES


def test_ajouter_departements_lit_les_colonnes_nommees_par_schema_source():
    # Chaque source nomme ses colonnes à sa façon : la cascade passe par `cols`
    # (clé schema_source -> colonne réelle), pas par des libellés fixes (#232).
    df = pd.DataFrame({
        "Dépt op.": ["42/Loire", None, None],
        "CP / zip code": ["13001", "75011", None],
        "Montant UE": [1.0, 2.0, 3.0],
    })
    cols = {"departement": "Dépt op.", "cp_beneficiaire": "CP / zip code", "zone": "Absente"}

    resultat = ajouter_departements(df, cols)

    # Le manquant peut sortir en None ou en NaN selon le type que pandas infère :
    # le dashboard le teste par notna(), le test fait de même.
    assert resultat["dept"].iloc[:2].tolist() == ["42", "75"]
    assert pd.isna(resultat["dept"].iloc[2])
    assert resultat["dept_source"].tolist() == ["opération", "approximé", "inconnu"]
    assert resultat["Montant UE"].tolist() == [1.0, 2.0, 3.0]  # le reste est conservé
    assert "dept" not in df.columns  # pas de modification en place


def test_ajouter_departements_sur_une_source_sans_aucun_champ_de_localisation():
    # Nouvelle-Aquitaine 2014-2020 : ni département, ni code postal (#95).
    resultat = ajouter_departements(pd.DataFrame({"Montant UE": [1.0, 2.0]}), {})
    assert resultat["dept"].isna().all()
    assert resultat["dept_source"].tolist() == ["inconnu", "inconnu"]


def test_le_dashboard_affiche_les_libelles_du_pipeline():
    # Contrat des libellés d'origine : une seule constante, importée par l'affichage.
    from utils import departments as affichage

    assert affichage.DEPT_SOURCES is DEPT_SOURCES


# --- Tableau « Détail par département » (issue #157, écart D3) ----------------------


def test_le_tableau_par_departement_totalise_100_pourcent_de_la_region():
    """Pages 1 et 5 : une ligne par département de la région, puis « Non réparti » et
    « Hors périmètre » — sans ces deux lignes, des opérations disparaîtraient du total (#100)."""
    from utils.departments import tableau_departements

    df = pd.DataFrame({
        "dept": ["29", "35", "35", None, "75"],
        "Montant UE": [100.0, 50.0, 70.0, 30.0, 999.0],
    })
    tableau, color_range = tableau_departements(df, "Bretagne")

    assert tableau["Département"].tolist() == ["35", "29", "Non réparti (région entière)", "Hors périmètre (autre région)"]
    assert tableau["Montant UE total"].tolist() == [120.0, 100.0, 30.0, 999.0]
    assert tableau["Nb projets"].tolist() == [2, 1, 1, 1]
    assert tableau["Montant UE total"].sum() == df["Montant UE"].sum()
    # L'échelle de la carte ne voit que les départements : la ligne « Hors périmètre », la
    # plus grosse ici, écraserait sinon toutes les couleurs.
    assert color_range == [0, 120.0]


def test_sans_operation_non_rattachee_ni_hors_region_le_tableau_n_a_que_des_departements():
    from utils.departments import tableau_departements

    tableau, _ = tableau_departements(pd.DataFrame({"dept": ["29"], "Montant UE": [10.0]}), "Bretagne")
    assert tableau["Département"].tolist() == ["29"]
