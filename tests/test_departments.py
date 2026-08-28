"""Rattachement départemental (`dashboard/utils/departments.py`) — la cascade dont
dépendent toutes les cartes par département, sur les deux périodes (`assign_departement`
est une fonction partagée, pas propre à 2014-2020).

`zone_dept` est la brique qui a motivé l'issue #92 : le champ Zone (Synergie) porte le
lieu réel du projet, validé à 100 % d'accord avec le champ pipeline "Département de
l'opération" sur les données réelles (voir son docstring) — d'où sa priorité sur
l'approximation par code postal du bénéficiaire (siège, pas lieu du projet).
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.departments import DEPT_SOURCES, assign_departement, cp_to_dept, zone_dept  # noqa: E402


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


def test_assign_departement_priorite_au_champ_pipeline_sur_zone():
    op = {"Département de l’opération": "42/Loire", "Zone": "DEPT/075/Paris"}
    assert assign_departement(op) == ("42", "opération")


def test_assign_departement_zone_avant_code_postal():
    op = {"Zone": "DEPT/075/Paris", "Code postal du bénéficiaire": "13001"}
    assert assign_departement(op) == ("75", "zone")


def test_assign_departement_zone_resout_corse_la_ou_le_code_postal_echoue():
    op = {"Zone": "COMM/2A004/Ajaccio", "Code postal du bénéficiaire": "20000"}
    assert cp_to_dept("20000") is None  # le cas que Zone débloque
    assert assign_departement(op) == ("2A", "zone")


def test_assign_departement_repli_sur_code_postal_si_zone_absente():
    op = {"Code postal du bénéficiaire": "13001"}
    assert assign_departement(op) == ("13", "approximé")


def test_assign_departement_repli_sur_nom_si_rien_dautre():
    op = {"Nom du bénéficiaire": "Ville de Bastia"}
    assert assign_departement(op) == ("2B", "nom du bénéficiaire")


def test_assign_departement_inconnu_si_rien_ne_resout():
    assert assign_departement({}) == (None, "inconnu")


def test_dept_sources_contient_zone():
    assert "zone" in DEPT_SOURCES
