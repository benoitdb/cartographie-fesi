"""La couture entre le pipeline et le chargeur Metabase (issue #134).

Le dépôt teste solidement chaque côté séparément — la suite du dashboard d'un
côté, `metabase/verify_*.py` de l'autre — mais **rien ne traversait la
frontière** entre les deux. La PR #132 (opérations en Parquet, issue #130) a
changé le format de sortie d'`ingest.py` sans que rien ne signale que
`metabase/load_data.py` lisait encore une clé JSON disparue : les deux côtés
vivent sur des branches différentes, et le chargeur exige Docker + PostgreSQL,
donc la CI ne le lance pas.

Ces tests couvrent la **lecture et le typage** — la partie qui casse quand le
format change — sans exiger de base de données. Le chargement SQL lui-même reste
hors couverture, c'est `verify_aggregates.py` qui s'en charge, stack allumée.

Ce qu'ils protègent, appris en le voyant échouer plutôt qu'en l'anticipant :
`valeur_python` doit ramener les valeurs Parquet **au type que produisait le
JSON**, pas à un type Python quelconque. Trois conversions sont nécessaires
(ndarray, NaN/NaT, Timestamp) et la troisième n'a été trouvée qu'en chargeant
réellement — d'où le contrôle de sérialisabilité *effective* ci-dessous, qui
vaut mieux qu'une liste de types attendus.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "metabase"))
sys.path.insert(0, str(RACINE / "data-pipeline"))
sys.path.insert(0, str(RACINE / "dashboard"))

pytest.importorskip("pandas", reason="dépendances du chargeur Metabase non installées")
pytest.importorskip("pyarrow", reason="pyarrow requis pour lire le Parquet")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

load_data = pytest.importorskip(
    "load_data", reason="metabase/load_data.py non importable (psycopg2 manquant ?)"
)


# --- valeur_python : les trois conversions, sur des cas construits -------------


def test_ndarray_devient_une_liste_python():
    """psycopg2 n'adapte pas un ndarray en TEXT[]. Le piège est latent : un
    tableau à un élément a une valeur de vérité définie, donc seules les
    opérations interrégionales (2 régions ou plus) font lever."""
    converti = load_data.valeur_python(np.array(["Bretagne", "Normandie"]))
    assert isinstance(converti, list)
    assert converti == ["Bretagne", "Normandie"]
    # Le test de vérité que fait `load_operations_for_source` doit passer.
    assert bool(converti) is True


@pytest.mark.parametrize(
    "absente",
    [float("nan"), pd.NaT, None],
    ids=["nan", "nat", "none"],
)
def test_valeur_absente_devient_none(absente):
    """None, jamais NaN : une valeur manquante passerait les tests
    `not in (None, "")` du constructeur de lignes et finirait insérée en 'nan'
    littéral (texte) ou en NaN numérique — que PostgreSQL accepte sans broncher,
    à la place du NULL attendu."""
    assert load_data.valeur_python(absente) is None


@pytest.mark.parametrize(
    "valeur",
    [pd.Timestamp("2015-01-01"), datetime(2015, 1, 1, 14, 30), date(2015, 1, 1)],
    ids=["timestamp", "datetime", "date"],
)
def test_date_devient_la_chaine_du_format_json(valeur):
    """La cible est **ce qu'écrivait `prepare_for_json`** ('%Y-%m-%d'), pas un
    type Python quelconque : c'est ce qui rend les deux chemins de lecture
    indiscernables. Un Timestamp laissé tel quel fait lever `json.dumps` sur la
    colonne JSONB `extra` — le chargement plante à la quatrième source."""
    assert load_data.valeur_python(valeur) == "2015-01-01"


def test_les_valeurs_deja_bonnes_ne_sont_pas_touchees():
    """Sans quoi le test passerait aussi sur une fonction qui écrase tout."""
    assert load_data.valeur_python("Bretagne") == "Bretagne"
    assert load_data.valeur_python(42) == 42
    assert load_data.valeur_python(3.14) == 3.14
    assert load_data.valeur_python(True) is True


# --- lire_operations : les deux formats, sur les fixtures committées -----------

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dashboard"


@pytest.fixture
def fixture_comme_source(monkeypatch):
    """Fait lire au chargeur les fixtures committées plutôt que `data/processed/`,
    gitignoré et absent d'un clone nu — même principe que `donnees_fixture` pour
    le dashboard."""
    monkeypatch.setattr(load_data, "DATA_DIR", FIXTURE)


# Les fixtures ne sont au format Parquet qu'une fois cette branche fusionnée avec
# `main` (PR #132). Avant, `lire_operations` emprunte son repli JSON : les tests
# qui prétendent exercer le Parquet doivent se déclarer sautés plutôt que de
# passer en testant l'autre chemin — un test vert sur ce qu'il ne teste pas est
# pire que pas de test.
besoin_parquet = pytest.mark.skipif(
    not (FIXTURE / "data.parquet").exists(),
    reason="fixtures encore au format JSON (branche pas encore fusionnée avec main)",
)


@besoin_parquet
def test_lit_les_operations_depuis_le_parquet(fixture_comme_source):
    ops = load_data.lire_operations("2021-2027", "data.json")
    assert ops, "aucune opération lue"
    assert isinstance(ops[0], dict)


def test_lit_les_operations_quel_que_soit_le_format(fixture_comme_source):
    """Vaut avant comme après la fusion : c'est le contrat de `lire_operations`."""
    ops = load_data.lire_operations("2021-2027", "data.json")
    assert ops, "aucune opération lue"
    assert isinstance(ops[0], dict)
    assert "regions_modernes" in ops[0]


def test_source_absente_renvoie_none(fixture_comme_source):
    """Les fichiers régionaux hors-Synergie sont gitignorés : leur absence est un
    repli normal, pas une erreur — le chargeur doit sauter la source."""
    assert load_data.lire_operations("bidon", "data_inexistant.json") is None


@besoin_parquet
@pytest.mark.parametrize(
    "fichier",
    [
        "data.json",
        "data_2014-2020.json",
        "data_2014-2020_normandie.json",
        "data_2014-2020_nouvelle_aquitaine.json",
        "data_2014-2020_bretagne_officiel.json",
        "data_2014-2020_pon_fse.json",
    ],
)
def test_toute_valeur_lue_est_serialisable_en_json(fichier, fixture_comme_source):
    """**Le test qui aurait attrapé la régression réelle.** `load_data` verse
    dans la colonne JSONB `extra` toute colonne source sans équivalent SQL — donc
    n'importe quelle valeur peut finir dans un `json.dumps`. Vérifier la
    sérialisabilité *effective* attrape les types qu'on n'a pas pensé à lister :
    c'est un `Timestamp` non converti qui a fait planter le chargement en réel,
    alors que les contrôles de types anticipés passaient tous."""
    ops = load_data.lire_operations("source", fichier)
    assert ops, f"{fichier} : aucune opération lue"

    for index, op in enumerate(ops):
        try:
            json.dumps(op, ensure_ascii=False)
        except TypeError as exc:
            coupables = {
                cle: type(val).__name__
                for cle, val in op.items()
                if not _serialisable(val)
            }
            pytest.fail(f"{fichier}, opération {index} : {exc} — colonnes {coupables}")


def _serialisable(val):
    try:
        json.dumps(val)
        return True
    except TypeError:
        return False


@besoin_parquet
@pytest.mark.parametrize(
    "fichier",
    ["data.json", "data_2014-2020.json", "data_2014-2020_pon_fse.json"],
)
def test_regions_modernes_supporte_le_test_de_verite(fichier, fixture_comme_source):
    """Reproduit littéralement ce que fait `load_operations_for_source`. Un
    ndarray à deux éléments lève ici, et seulement sur les interrégionales — 13
    opérations sur 16 625 en 2021-2027, assez peu pour passer un contrôle
    superficiel et assez pour faire échouer un chargement complet."""
    for op in load_data.lire_operations("source", fichier):
        regions = op.get("regions_modernes") or []
        _ = regions[0] if regions else None
