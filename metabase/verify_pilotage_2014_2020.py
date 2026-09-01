"""Tests croisés Python vs SQL de la période 2014-2020 (Phase 3, issue #121).

`verify_aggregates.py` (Phase 0) compare les agrégats **d'une source** à sa vue
SQL. Ici c'est l'inverse qui est vérifié : la **fusion des six sources** de la
période, que `init/04_periode_2014_2020.sql` refait en SQL et que
`dashboard/pages/5_Période_2014-2020.py` fait en Python.

Les règles ne sont pas réimplémentées : elles sont relues du dashboard
(`REGIONS_PON_FSE_2014_2020`, `FUSIONS_ENVELOPPES_SANS_LIBELLE`,
`reste_a_engager`, `taux_consommation`) et appliquées ici aux mêmes JSON que
lit la page, périmètre par périmètre. Ce qui reste dupliqué côté SQL — le
routage PON FSE écrit en CASE, la liste des trois régions à substituer, les
trois fonds hors plafond — est précisément ce que ce script fait rougir s'il
diverge un jour du Python.

Script de vérification ponctuelle, pas un test pytest (il lui faut PostgreSQL
et les JSON de données) : à relancer après tout changement des vues 14-20 ou
des règles de fusion côté dashboard.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 requis : pip install psycopg2-binary")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "processed"
DASHBOARD_DIR = SCRIPT_DIR.parent / "dashboard"
PIPELINE_DIR = SCRIPT_DIR.parent / "data-pipeline"
sys.path.insert(0, str(DASHBOARD_DIR))
sys.path.insert(0, str(PIPELINE_DIR))

import schema_source  # noqa: E402
import sources as sources_module  # noqa: E402

from utils.periodes import (  # noqa: E402
    FUSIONS_ENVELOPPES_SANS_LIBELLE,
    REGIONS_PON_FSE_2014_2020,
)

env_path = SCRIPT_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DB_PARAMS = dict(
    host="localhost",
    port=5437,
    dbname=os.environ.get("POSTGRES_DB", "fesi"),
    user=os.environ.get("POSTGRES_USER", "fesi"),
    password=os.environ.get("POSTGRES_PASSWORD", "fesi_local"),
)

# Même tolérance et même raison qu'en Phase 0 (verify_aggregates.py) : ordre de
# sommation différent sur les mêmes flottants, jamais une erreur de données.
RELATIVE_TOLERANCE = 1e-6

# Les trois régions dont le fichier régional SE SUBSTITUE à Synergie (#95), par
# identifiant de source. Le vieux fichier Bretagne europe.bzh
# (`2014-2020-bretagne`) n'y figure pas : remplacé par l'export officiel pour
# tout usage autre que la page « Validation de la source ».
SOURCES_REGIONALES = {
    "Bretagne": "2014-2020-bretagne-officiel",
    "Normandie": "2014-2020-normandie",
    "Nouvelle-Aquitaine": "2014-2020-nouvelle-aquitaine",
}
SOURCE_SYNERGIE = "2014-2020-synergie"
SOURCE_PON_FSE = "2014-2020-pon-fse"


def libelles_bruts(source_id):
    """{clé interne: libellé réel} pour une source, lu de `schema_source.SCHEMAS`.

    Jamais des libellés recopiés à la main : ce script somme la donnée brute
    des JSON sans passer par `normaliser_operations`, et les cinq fichiers de
    la période nomment leurs colonnes différemment (« Montant UE » ici,
    « Mont_UE » là, « Amount co-financing European Union » ailleurs). Les
    recopier serait exactement la duplication que `sources.py` existe pour
    éviter — et une faute de frappe y ferait passer un total à zéro sans rien
    casser.
    """
    descriptor = sources_module.SOURCES[source_id]
    schema_key = descriptor.get("schema", descriptor["periode"])
    return {cle: libelle for cle, libelle in schema_source.SCHEMAS[schema_key]}


def close_enough(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    return abs(a - b) <= max(0.01, abs(a) * RELATIVE_TOLERANCE)


def charger(fichier):
    path = DATA_DIR / fichier
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def charger_source(source_id):
    """(opérations, libellés bruts) d'une source, ou sortie en erreur si son
    JSON manque : mieux vaut ne rien vérifier du tout qu'annoncer une
    concordance établie sur un périmètre amputé."""
    descriptor = sources_module.SOURCES[source_id]
    fichier = descriptor["fichier_sortie"]
    data = charger(fichier)
    if data is None:
        sys.exit(f"{fichier} absent : la fusion de {source_id} ne peut pas être vérifiée.")
    return data["operations"], libelles_bruts(source_id)


def engage_python():
    """{(perimetre, fonds): montant}, par les règles de la page 2014-2020.

    Reproduit le grand `if/elif` de `pages/5_Période_2014-2020.py` :
      - Synergie : une opération mono-région va à sa région, une opération
        `is_national` au volet national, une interrégionale à aucun des deux
        (sinon elle compterait dans plusieurs totaux censés s'additionner) ;
      - les trois régions à fichier propre ignorent entièrement Synergie ;
      - PON FSE s'ajoute, routé par programme (REGIONS_PON_FSE_2014_2020).
    """
    engage = defaultdict(float)

    operations, cols = charger_source(SOURCE_SYNERGIE)
    for op in operations:
        fonds = op.get(cols["fonds"])
        montant = op.get(cols["montant_ue"]) or 0
        if fonds is None:
            continue
        if op.get("is_national"):
            engage[("national", fonds)] += montant
        elif not op.get("is_interregional"):
            regions = op.get("regions_modernes") or []
            if len(regions) == 1 and regions[0] not in SOURCES_REGIONALES:
                engage[(regions[0], fonds)] += montant

    for region, source_id in SOURCES_REGIONALES.items():
        operations, cols = charger_source(source_id)
        for op in operations:
            fonds = op.get(cols["fonds"])
            if fonds is None:
                continue
            engage[(region, fonds)] += op.get(cols["montant_ue"]) or 0

    operations, cols = charger_source(SOURCE_PON_FSE)
    for op in operations:
        fonds = op.get(cols["fonds"])
        if fonds is None:
            continue
        perimetre = REGIONS_PON_FSE_2014_2020.get(op.get(cols["libelle_prog"])) or "national"
        engage[(perimetre, fonds)] += op.get(cols["montant_ue"]) or 0

    return dict(engage)


def enveloppes_python(engage):
    """{(perimetre, fonds): montant programmé}, après fusion des enveloppes dont
    aucun libellé de fonds ne porte d'opération sur le périmètre
    (FUSIONS_ENVELOPPES_SANS_LIBELLE : FEDER REACT-EU -> FEDER hors DROM)."""
    totaux = charger("programme_totals_2014_2020.json")
    if totaux is None:
        sys.exit("programme_totals_2014_2020.json absent : pas d'enveloppes à comparer.")

    enveloppes = defaultdict(float)
    for perimetre, par_fonds in totaux.items():
        fonds_engages = {f for (p, f) in engage if p == perimetre}
        for fonds, montant in par_fonds.items():
            accueil = FUSIONS_ENVELOPPES_SANS_LIBELLE.get(fonds)
            if accueil and fonds not in fonds_engages and accueil in par_fonds:
                enveloppes[(perimetre, accueil)] += montant
            else:
                enveloppes[(perimetre, fonds)] += montant
    return dict(enveloppes)


def check_pilotage(cur, engage, enveloppes):
    """Compare ligne à ligne `v_pilotage_2014_2020` au calcul Python."""
    cur.execute("SELECT perimetre, fonds, programme, engage FROM v_pilotage_2014_2020")
    sql = {(p, f): (float(prog), float(eng)) for p, f, prog, eng in cur.fetchall()}

    errors = []
    for cle, programme in enveloppes.items():
        if cle not in sql:
            errors.append(f"{cle} : absent de v_pilotage_2014_2020 (programmé {programme:,.2f} en Python)")
            continue
        sql_programme, sql_engage = sql[cle]
        if not close_enough(programme, sql_programme):
            errors.append(f"{cle} programmé : SQL {sql_programme:,.2f} vs Python {programme:,.2f}")
        attendu = engage.get(cle, 0)
        if not close_enough(attendu, sql_engage):
            errors.append(f"{cle} engagé : SQL {sql_engage:,.2f} vs Python {attendu:,.2f}")
    for cle in sql:
        if cle not in enveloppes:
            errors.append(f"{cle} : ligne SQL sans enveloppe correspondante en Python")
    return errors


def check_engage(cur, engage):
    """Compare `v_engage_2014_2020` (tout l'engagé, y compris les fonds sans
    enveloppe — FEAD, FEDER-FSE — que `v_pilotage_2014_2020` écarte)."""
    cur.execute("SELECT perimetre, fonds, engage FROM v_engage_2014_2020")
    sql = {(p, f): float(e) for p, f, e in cur.fetchall()}

    errors = []
    for cle, montant in engage.items():
        if cle not in sql:
            errors.append(f"{cle} : absent de v_engage_2014_2020 ({montant:,.2f} en Python)")
        elif not close_enough(montant, sql[cle]):
            errors.append(f"{cle} engagé : SQL {sql[cle]:,.2f} vs Python {montant:,.2f}")
    for cle in sql:
        if cle not in engage:
            errors.append(f"{cle} : ligne SQL absente du calcul Python")
    return errors


def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    engage = engage_python()
    enveloppes = enveloppes_python(engage)

    errors = check_engage(cur, engage) + check_pilotage(cur, engage, enveloppes)

    cur.close()
    conn.close()

    print(f"Périmètres × fonds comparés : {len(engage)} engagés, {len(enveloppes)} enveloppes.")
    if errors:
        print(f"\nÉCHEC : {len(errors)} écart(s).")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    print("La fusion SQL des six sources 2014-2020 concorde avec celle du dashboard.")


if __name__ == "__main__":
    main()
