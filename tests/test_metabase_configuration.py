import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "metabase"))

import configuration  # noqa: E402
import provision_roles  # noqa: E402


def test_connexion_du_chargeur_exige_des_identifiants_explicites(monkeypatch):
    monkeypatch.setattr(configuration, "charger_env", lambda environnement=None: {"POSTGRES_DB": "fesi"})
    with pytest.raises(RuntimeError, match="FESI_LOADER_USER"):
        configuration.connexion_fesi("loader")


def test_connexion_lecteur_n_utilise_pas_le_compte_chargeur():
    env = {
        "POSTGRES_DB": "fesi",
        "FESI_LOADER_USER": "chargeur",
        "FESI_LOADER_PASSWORD": "secret-chargeur",
        "FESI_READER_USER": "lecteur",
        "FESI_READER_PASSWORD": "secret-lecteur",
    }
    assert configuration.connexion_fesi("reader", env)["user"] == "lecteur"


class FragmentSQL(str):
    def format(self, *arguments):
        return FragmentSQL(super().format(*arguments))


class SQLSimule:
    @staticmethod
    def SQL(texte):
        return FragmentSQL(texte)

    @staticmethod
    def Identifier(nom):
        return f'"{nom}"'


class CurseurProprietes:
    def __init__(self):
        self.executions = []

    def execute(self, requete, parametres=None):
        self.executions.append((str(requete), parametres))

    def fetchall(self):
        return [("r", "databasechangelog"), ("S", "metabase_id_seq"), ("v", "v_usage")]


def test_transfert_metabase_est_limite_aux_objets_public_et_idempotent():
    cur = CurseurProprietes()

    provision_roles.transferer_propriete_public(cur, "metabase_app", SQLSimule)

    recherche, parametres = cur.executions[0]
    assert "n.nspname = 'public'" in recherche
    assert "c.relkind IN ('r', 'p', 'S', 'v', 'm')" in recherche
    assert "FROM pg_depend AS d" in recherche
    assert "c.relowner <>" in recherche
    assert parametres == ("metabase_app",)
    assert [requete for requete, _ in cur.executions[1:]] == [
        'ALTER TABLE "databasechangelog" OWNER TO "metabase_app"',
        'ALTER SEQUENCE "metabase_id_seq" OWNER TO "metabase_app"',
        'ALTER VIEW "v_usage" OWNER TO "metabase_app"',
        'ALTER SCHEMA public OWNER TO "metabase_app"',
    ]
