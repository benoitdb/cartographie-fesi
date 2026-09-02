"""Vérification chiffrée Streamlit vs Metabase (Phase 4, issue #121).

Les deux scripts précédents comparent Python et SQL en attaquant PostgreSQL
directement : ils valident les **vues**, pas ce qu'un utilisateur lit. Entre une
vue juste et un chiffre affiché il reste trois couches propres à Metabase — le
SQL de la carte, son template-tag, et le `parameter_mapping` du dashboard — dont
aucune n'était couverte, et dont l'une échoue **en silence** : un paramètre mal
câblé n'est pas une erreur, le filtre est simplement ignoré et la carte répond un
chiffre non filtré parfaitement plausible (cf. README, gotchas de l'API).

Ce script ne se connecte donc jamais à PostgreSQL : il interroge chaque carte par
l'endpoint dashboard de l'API, filtres appliqués, comme le fait le navigateur, et
compare à ce qu'affiche le dashboard Streamlit pour le même périmètre. Les règles
métier ne sont pas réécrites — `taux_consommation`/`reste_a_engager` sont
importées de `dashboard/utils/pilotage.py`, la fusion des six sources 2014-2020
de `verify_pilotage_2014_2020.py`, les plafonds de
`dashboard/utils/cofinancement.py`.

**Se lance avec le venv racine**, pas `metabase/venv` : il lui faut Streamlit
(que `utils/pilotage.py` importe), et pas psycopg2.

    venv/bin/python metabase/verify_dashboards.py

Un premier passage (2 sept. 2026) avait trouvé quatre écarts de définition —
Metabase et Streamlit ne comptant sciemment pas la même chose au même endroit.
Les quatre ont été arbitrés dans la foulée (issue #121, Phase 4) : le script ne
distingue donc plus deux catégories de sortie, tout écart chiffré est un échec.
  - l'engagement cumulé cumule désormais sur la même date des deux côtés (date de
    début d'opération) ;
  - la carte KPI 2014-2020 exclut désormais les dossiers sans fonds renseigné,
    comme le filtre Fonds de Streamlit ;
  - le taux de cofinancement affiché est désormais homogène des deux côtés
    (toujours recalculé, jamais le taux déclaré par un fichier régional — #127) ;
  - `detect_cofinancement_superieur_plafond` applique désormais la même
    tolérance relative que la comparaison SQL en NUMERIC (#126).
"""

import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT_DIR / "dashboard"))

import load_data  # noqa: E402  (parse_date, pour reproduire le chargement à l'identique)
import setup_metabase as setup  # noqa: E402  (noms de dashboards, ids de paramètres, défauts)
from verify_pilotage_2014_2020 import (  # noqa: E402
    close_enough,
    engage_python,
    enveloppes_python,
    operations_par_perimetre,
)

from utils import cofinancement  # noqa: E402
from utils.data_loader import (  # noqa: E402
    CATEGORIES_UE_2014_2020_PATH,
    DATA_PATH,
    PROGRAMME_TOTALS_PATH,
)
from utils.periodes import SEUIL_ECART_TAUX_DECLARE  # noqa: E402
from utils.pilotage import reste_a_engager, taux_consommation  # noqa: E402
from utils.stats import TOLERANCE_RELATIVE_PLAFOND  # noqa: E402

MB_URL = setup.MB_URL

# Libellés de colonnes 2021-2027, tels que le dashboard Streamlit les lit
# (`data.json` n'est pas normalisé, c'est la période de référence du projet).
FONDS = "Fonds"
MONTANT = "Montant UE"
DATE_DEBUT = "Date de début de l'opération"


# ------------------------------------------------------------------ API Metabase


def interroger(session, dash, nom_carte, valeurs=None):
    """Lignes d'UNE carte du dashboard, interrogée par l'endpoint dashboard —
    celui qui applique les `parameter_mappings`, donc celui du navigateur.

    `valeurs` : {id de paramètre de dashboard: valeur}, None = pas de filtre.

    Une carte qui n'a pas de mapping pour un paramètre demandé arrête le script :
    c'est le mode de panne silencieux que ce fichier existe pour attraper (le
    filtre serait ignoré sans la moindre erreur), et il est structurel — le
    signaler comme un écart chiffré parmi d'autres le noierait.
    """
    dc = next((d for d in dash["dashcards"] if d["card"]["name"] == nom_carte), None)
    if dc is None:
        sys.exit(f"{dash['name']} : carte « {nom_carte} » introuvable — relancer setup_metabase.py ?")

    parametres = []
    for param_id, valeur in (valeurs or {}).items():
        if valeur is None:
            continue
        mapping = next((m for m in dc["parameter_mappings"] if m["parameter_id"] == param_id), None)
        if mapping is None:
            sys.exit(
                f"{dash['name']} / « {nom_carte} » : aucun mapping pour le paramètre "
                f"{param_id} — le filtre serait ignoré en silence."
            )
        param = next(p for p in dash["parameters"] if p["id"] == param_id)
        parametres.append(
            {"id": param_id, "type": param["type"], "target": mapping["target"], "value": [valeur]}
        )

    r = session.post(
        f"{MB_URL}/api/dashboard/{dash['id']}/dashcard/{dc['id']}/card/{dc['card_id']}/query",
        json={"parameters": parametres},
    )
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != "completed":
        sys.exit(f"{dash['name']} / « {nom_carte} » : {payload.get('error')}")

    noms = [c["name"] for c in payload["data"]["cols"]]
    return [dict(zip(noms, ligne, strict=True)) for ligne in payload["data"]["rows"]]


def scalaire(lignes):
    """Valeur unique d'une carte `scalar` — 0 quand la requête ne ramène rien ou
    un SUM sur zéro ligne (Metabase affiche une case vide, pas une erreur)."""
    if not lignes:
        return 0
    valeur = next(iter(lignes[0].values()))
    return 0 if valeur is None else valeur


def dashboards_fesi(session):
    """{nom: dashboard complet} pour les cinq dashboards du projet."""
    index = {d["name"]: d["id"] for d in session.get(f"{MB_URL}/api/dashboard").json()}
    noms = [
        setup.DASHBOARD_NAME,
        setup.REGIONAL_DASHBOARD_NAME,
        setup.COMPARATEUR_DASHBOARD_NAME,
        setup.NATIONAL_DASHBOARD_NAME,
        setup.DASHBOARD_2014_2020_NAME,
    ]
    manquants = [n for n in noms if n not in index]
    if manquants:
        sys.exit("Dashboards absents de l'instance : " + ", ".join(manquants))
    return {n: session.get(f"{MB_URL}/api/dashboard/{index[n]}").json() for n in noms}


# ------------------------------------------------------- Références côté Streamlit


def charger_references():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    with open(PROGRAMME_TOTALS_PATH, encoding="utf-8") as f:
        programme_totals = json.load(f)
    with open(CATEGORIES_UE_2014_2020_PATH, encoding="utf-8") as f:
        categories = json.load(f)
    return data, programme_totals, categories


def pilotage_python(programme_par_fonds, engage_par_fonds):
    """Les lignes de pilotage d'un périmètre, telles que les construisent les
    pages Streamlit : une ligne par fonds **programmé** (un engagé sans enveloppe
    n'a pas de taux à afficher), et les deux formules importées de
    `utils.pilotage` plutôt que réécrites."""
    return {
        fonds: {
            "programme": programme,
            "engage": engage_par_fonds.get(fonds, 0),
            "taux": taux_consommation(engage_par_fonds.get(fonds, 0), programme),
            "reste_a_engager": max(programme - engage_par_fonds.get(fonds, 0), 0),
        }
        for fonds, programme in programme_par_fonds.items()
    }


def comparer_pilotage(lignes_mb, attendu, contexte):
    """Compare les lignes d'une carte de pilotage, colonne par colonne, puis le
    reste à engager **agrégé** — celui-ci passe par `reste_a_engager()` du
    dashboard, appliqué aux lignes que Metabase vient de renvoyer : c'est la
    règle du #62 (somme des restes par fonds, chacun planché à 0) vérifiée sur
    la donnée réellement affichée, pas sur une reconstitution."""
    erreurs = []
    par_fonds = {ligne["fonds"]: ligne for ligne in lignes_mb}
    for fonds, ref in attendu.items():
        ligne = par_fonds.get(fonds)
        if ligne is None:
            erreurs.append(f"{contexte} : fonds {fonds} absent de Metabase (programmé {ref['programme']:,.2f})")
            continue
        for colonne, valeur in ref.items():
            if not close_enough(valeur, ligne[colonne]):
                erreurs.append(
                    f"{contexte} / {fonds} / {colonne} : Metabase {float(ligne[colonne]):,.4f} "
                    f"vs Streamlit {valeur:,.4f}"
                )
    for fonds in par_fonds:
        if fonds not in attendu:
            erreurs.append(f"{contexte} : fonds {fonds} affiché par Metabase, absent côté Streamlit")

    if lignes_mb and attendu and not erreurs:
        reste_mb = reste_a_engager(pd.DataFrame(lignes_mb))
        reste_ref = reste_a_engager(pd.DataFrame(list(attendu.values())))
        if not close_enough(reste_ref, reste_mb):
            erreurs.append(f"{contexte} / reste à engager agrégé : Metabase {reste_mb:,.2f} vs Streamlit {reste_ref:,.2f}")
    return erreurs


def comparer_series(lignes_mb, attendu, cle, colonne, contexte):
    """Compare une carte qui renvoie une ligne par catégorie ({clé: valeur})."""
    erreurs = []
    obtenu = {ligne[cle]: ligne[colonne] for ligne in lignes_mb}
    for k, valeur in attendu.items():
        if k not in obtenu:
            erreurs.append(f"{contexte} : {k} absent de Metabase ({valeur:,.2f} côté Streamlit)")
        elif not close_enough(valeur, obtenu[k]):
            erreurs.append(f"{contexte} / {k} : Metabase {float(obtenu[k]):,.2f} vs Streamlit {valeur:,.2f}")
    for k in obtenu:
        if k not in attendu:
            erreurs.append(f"{contexte} : {k} affiché par Metabase, absent côté Streamlit")
    return erreurs


# ------------------------------------------------------ Dashboards 2021-2027


def check_vue_nationale(session, dash, agg, data):
    """« FESI — Vue nationale 2021-2027 » : les cinq cartes, sans filtre puis
    pour chacun des trois fonds — c'est le seul dashboard dont le filtre porte
    sur toutes les cartes à la fois."""
    erreurs, n = [], 0
    by_fonds, by_region, by_region_fonds = agg["by_fonds"], agg["by_region"], agg["by_region_fonds"]

    for fonds in [None, *sorted(by_fonds)]:
        valeurs = {setup.DASHBOARD_PARAM_ID: fonds}
        selection = sorted(by_fonds) if fonds is None else [fonds]
        libelle = "sans filtre" if fonds is None else f"fonds={fonds}"
        contexte = f"Vue nationale ({libelle})"

        attendu_count = sum(by_fonds[f]["count"] for f in selection)
        attendu_montant = sum(by_fonds[f]["montant_ue_total"] for f in selection)

        obtenu = scalaire(interroger(session, dash, "Nombre d'opérations", valeurs))
        if not close_enough(attendu_count, obtenu):
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {obtenu} vs Streamlit {attendu_count}")
        obtenu = scalaire(interroger(session, dash, "Montant UE total", valeurs))
        if not close_enough(attendu_montant, obtenu):
            erreurs.append(f"{contexte} / montant UE total : Metabase {float(obtenu):,.2f} vs Streamlit {attendu_montant:,.2f}")
        n += 2

        erreurs += comparer_series(
            interroger(session, dash, "Montant UE par fonds", valeurs),
            {f: by_fonds[f]["montant_ue_total"] for f in selection},
            "fonds", "montant_ue_total", f"{contexte} / par fonds",
        )
        n += len(selection)

        # La carte région suit le filtre : sans filtre c'est `by_region` (agrégat
        # du pipeline), avec filtre c'est ce que Streamlit recalcule par
        # `compute_by_region` sur les opérations du fonds — soit `by_region_fonds`.
        if fonds is None:
            attendu_regions = {r: v["montant_ue_total"] for r, v in by_region.items()}
        else:
            attendu_regions = {
                v["region"]: v["montant_ue_total"]
                for v in by_region_fonds.values()
                if v["fonds"] == fonds
            }
        erreurs += comparer_series(
            interroger(session, dash, "Montant UE par région", valeurs),
            attendu_regions, "region", "montant_ue_total", f"{contexte} / par région",
        )
        n += len(attendu_regions)

        # Engagement cumulé : le dernier point de la courbe est le cumul total.
        # Alignée sur `build_trajectoire` (arbitrage Phase 4, #121) : les deux
        # cumulent désormais sur la date de DÉBUT D'OPÉRATION, plus sur la date de
        # première convention — même colonne, donc un vrai écart chiffré ici.
        lignes = interroger(session, dash, "Engagement cumulé", valeurs)
        cumul_mb = float(lignes[-1]["montant_cumule"]) if lignes else 0
        cumul_ref = sum(
            op[MONTANT] or 0
            for op in data["operations"]
            if (fonds is None or op.get(FONDS) == fonds) and load_data.parse_date(op.get(DATE_DEBUT))
        )
        if not close_enough(cumul_ref, cumul_mb):
            erreurs.append(f"{contexte} / engagement cumulé : Metabase {cumul_mb:,.2f} vs Streamlit {cumul_ref:,.2f}")
        n += 1
    return erreurs, n


def check_vue_regionale(session, dash, agg, programme_totals):
    """« FESI — Vue régionale 2021-2027 », région par région : toutes celles que
    le dashboard Streamlit propose, pas seulement le défaut."""
    erreurs, n = [], 0
    by_region, by_region_fonds = agg["by_region"], agg["by_region_fonds"]

    for region in sorted(by_region):
        valeurs = {setup.REGIONAL_PARAM_ID: region}
        contexte = f"Vue régionale ({region})"

        obtenu = scalaire(interroger(session, dash, "Région — Montant UE total", valeurs))
        if not close_enough(by_region[region]["montant_ue_total"], obtenu):
            erreurs.append(f"{contexte} / montant UE total : Metabase {float(obtenu):,.2f} vs Streamlit {by_region[region]['montant_ue_total']:,.2f}")
        obtenu = scalaire(interroger(session, dash, "Région — Nombre d'opérations", valeurs))
        if not close_enough(by_region[region]["count"], obtenu):
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {obtenu} vs Streamlit {by_region[region]['count']}")
        n += 2

        engage_region = {
            v["fonds"]: v["montant_ue_total"] for v in by_region_fonds.values() if v["region"] == region
        }
        erreurs += comparer_series(
            interroger(session, dash, "Région — Montant UE par fonds", valeurs),
            engage_region, "fonds", "montant_ue_total", f"{contexte} / par fonds",
        )
        n += len(engage_region)

        attendu = pilotage_python(programme_totals.get(region, {}), engage_region)
        erreurs += comparer_pilotage(
            interroger(session, dash, "Région — Programmé vs engagé par fonds", valeurs),
            attendu, f"{contexte} / pilotage",
        )
        n += len(attendu)
    return erreurs, n


def check_comparateur(session, dash, agg, programme_totals):
    """« FESI — Comparateur régions 2021-2027 » : deux paramètres indépendants sur
    des cartes communes, donc une carte qui ne câblerait qu'un des deux renverrait
    une moitié de résultat plausible. Les paires testées incluent le cas #62
    (Auvergne-Rhône-Alpes, dépassement FSE+) et un DROM."""
    erreurs, n = [], 0
    by_region, by_region_fonds = agg["by_region"], agg["by_region_fonds"]
    paires = [
        (setup.DEFAULT_REGION_A, setup.DEFAULT_REGION_B),
        ("Auvergne-Rhône-Alpes", "La Réunion"),
        ("Île-de-France", "Corse"),
    ]

    for region_a, region_b in paires:
        valeurs = {setup.COMPARATEUR_PARAM_A_ID: region_a, setup.COMPARATEUR_PARAM_B_ID: region_b}
        contexte = f"Comparateur ({region_a} / {region_b})"
        deux = [region_a, region_b]

        lignes = interroger(session, dash, "Comparateur — KPI par région", valeurs)
        obtenu = {ligne["region"]: ligne for ligne in lignes}
        for region in deux:
            if region not in obtenu:
                erreurs.append(f"{contexte} : {region} absente de la table KPI")
                continue
            for colonne, cle in [("n_operations", "count"), ("montant_ue_total", "montant_ue_total"), ("montant_ue_moyen", "montant_ue_moyen")]:
                if not close_enough(by_region[region][cle], obtenu[region][colonne]):
                    erreurs.append(f"{contexte} / {region} / {colonne} : Metabase {float(obtenu[region][colonne]):,.2f} vs Streamlit {by_region[region][cle]:,.2f}")
            n += 3
        for region in obtenu:
            if region not in deux:
                erreurs.append(f"{contexte} : {region} affichée sans avoir été demandée — un des deux filtres est ignoré")

        lignes = interroger(session, dash, "Comparateur — Montant UE par fonds", valeurs)
        obtenu = {(ligne["region"], ligne["fonds"]): ligne["montant_ue_total"] for ligne in lignes}
        attendu = {
            (v["region"], v["fonds"]): v["montant_ue_total"]
            for v in by_region_fonds.values()
            if v["region"] in deux
        }
        erreurs += comparer_series(
            [{"cle": k, "montant_ue_total": v} for k, v in obtenu.items()],
            {k: v for k, v in attendu.items()}, "cle", "montant_ue_total", f"{contexte} / par fonds",
        )
        n += len(attendu)

        lignes = interroger(session, dash, "Comparateur — Taux de consommation par fonds", valeurs)
        obtenu = {(ligne["region"], ligne["fonds"]): ligne["taux"] for ligne in lignes}
        attendu = {}
        for region in deux:
            engage_region = {v["fonds"]: v["montant_ue_total"] for v in by_region_fonds.values() if v["region"] == region}
            for fonds, ref in pilotage_python(programme_totals.get(region, {}), engage_region).items():
                attendu[(region, fonds)] = ref["taux"]
        erreurs += comparer_series(
            [{"cle": k, "taux": v} for k, v in obtenu.items()],
            attendu, "cle", "taux", f"{contexte} / taux",
        )
        n += len(attendu)
    return erreurs, n


def check_volet_national(session, dash, agg, data, programme_totals):
    """« FESI — Volet national 2021-2027 » : périmètre fixe, aucun paramètre —
    les chiffres doivent donc être ceux de `aggregates.national` sans condition."""
    erreurs, n = [], 0
    contexte = "Volet national"

    obtenu = scalaire(interroger(session, dash, "Volet national — Montant UE total"))
    if not close_enough(agg["national"]["montant_ue_total"], obtenu):
        erreurs.append(f"{contexte} / montant UE total : Metabase {float(obtenu):,.2f} vs Streamlit {agg['national']['montant_ue_total']:,.2f}")
    obtenu = scalaire(interroger(session, dash, "Volet national — Nombre d'opérations"))
    if not close_enough(agg["national"]["count"], obtenu):
        erreurs.append(f"{contexte} / nombre d'opérations : Metabase {obtenu} vs Streamlit {agg['national']['count']}")
    n += 2

    # Comme la page Streamlit : engagé national par fonds recalculé sur les
    # opérations `is_national`, il n'y a pas d'agrégat pré-calculé pour ce
    # découpage dans `data.json`.
    engage_national = defaultdict(float)
    for op in data["operations"]:
        if op.get("is_national") and op.get(FONDS):
            engage_national[op[FONDS]] += op[MONTANT] or 0
    engage_national = dict(engage_national)

    erreurs += comparer_series(
        interroger(session, dash, "Volet national — Montant UE par fonds"),
        engage_national, "fonds", "montant_ue_total", f"{contexte} / par fonds",
    )
    n += len(engage_national)

    attendu = pilotage_python(programme_totals.get("national", {}), engage_national)
    erreurs += comparer_pilotage(
        interroger(session, dash, "Volet national — Programmé vs engagé par fonds"),
        attendu, f"{contexte} / pilotage",
    )
    n += len(attendu)
    return erreurs, n


# ------------------------------------------------------ Dashboard 2014-2020


def cofinancement_python(operations, categories):
    """Résumé du cofinancement par (périmètre, fonds), et les opérations sur
    lesquelles Metabase et Streamlit ne rendent pas le même verdict de
    dépassement, ou pas le même signal de divergence.

    Périmètre commun aux deux : plafond de la région lu de `cofinancement`, fonds
    hors champ écartés par `est_hors_plafond`, comparaison au plafond HAUT de la
    fourchette (une région mixte n'a pas un plafond mais deux, et le fichier ne
    porte pas l'axe prioritaire qui trancherait). Le volet national n'a pas de
    catégorie de région : aucune ligne, comme le JOIN SQL qui l'écarte.

    Depuis l'arbitrage Phase 4 (#127/#126), le taux comparé au plafond est
    **homogène** des deux côtés — toujours montant/dépenses, jamais le taux
    déclaré par le fichier — donc les deux verdicts de dépassement doivent
    concorder exactement (Metabase en `NUMERIC`, Streamlit en flottant avec la
    tolérance relative de `detect_cofinancement_superieur_plafond`, cf. #126). Un
    écart ici serait donc un vrai bug, pas un écart de définition — il tombe dans
    `erreurs`, comme `check_engage`/`check_pilotage`.

    Le **signal de divergence** (taux déclaré vs recalculé, #127) est, lui,
    porté dans `resume` (`n_taux_divergents`, `montant_taux_divergents`) et
    comparé par l'appelant à la même carte Metabase que le reste du résumé —
    c'est un signal affiché sous condition côté Streamlit
    (`MENTION_TAUX_DECLARE_DIVERGENT`), mais son décompte doit concorder au
    chiffre près des deux côtés, donc une divergence de ce décompte est aussi
    une `erreur`, pas un écart de définition.
    """
    resume = {}
    erreurs = []
    for op in operations:
        infos = categories.get(op["perimetre"])
        fonds = op["fonds"]
        if infos is None or fonds is None or cofinancement.est_hors_plafond(fonds):
            continue
        montant, depenses = op["montant_ue"], op["depenses_eligibles"]
        if montant is None or depenses is None:
            continue

        plafond = cofinancement.plafond_intervalle_2014_2020(infos)
        plafond_min, plafond_max = plafond if plafond else (None, None)
        ligne = resume.setdefault(
            (op["perimetre"], fonds),
            {
                "categorie_ue": infos.get("categorie_ue"),
                "plafond_min": plafond_min,
                "plafond_max": plafond_max,
                "n_operations": 0,
                "n_depassements": 0,
                "montant_depassements": 0.0,
                "n_taux_divergents": 0,
                "montant_taux_divergents": 0.0,
            },
        )
        ligne["n_operations"] += 1

        # Même tolérance des deux côtés (arbitrage Phase 4, #126) : la vue SQL
        # l'applique aussi depuis que ce script a trouvé des opérations
        # programmées pile au plafond (arrondi à la centime côté source) que
        # seule une tolérance symétrique classe de la même façon ici et côté
        # Streamlit — sans quoi Metabase et Streamlit divergeraient sur des
        # centaines d'opérations plutôt que sur les 40 que #126 documente.
        depasse_sql = (
            depenses > 0
            and plafond_max is not None
            and Decimal(repr(montant)) / Decimal(repr(depenses))
            > Decimal(repr(plafond_max)) * (1 + Decimal(repr(TOLERANCE_RELATIVE_PLAFOND)))
        )
        if depasse_sql:
            ligne["n_depassements"] += 1
            ligne["montant_depassements"] += montant

        taux = op["taux_cofinancement"]
        depasse_streamlit = (
            taux is not None
            and plafond_max is not None
            and taux > plafond_max * (1 + TOLERANCE_RELATIVE_PLAFOND)
        )
        if depasse_streamlit != depasse_sql:
            erreurs.append(
                f"Période 2014-2020 ({op['perimetre']}) / cofinancement / {fonds} / "
                f"opération {op['numero_operation']} : dépassement Metabase={depasse_sql} "
                f"vs Streamlit={depasse_streamlit} (taux {taux!r}, plafond {plafond_max!r})"
            )

        declare = op["taux_declare"]
        divergent = declare is not None and taux is not None and abs(declare - taux) > SEUIL_ECART_TAUX_DECLARE
        if divergent:
            ligne["n_taux_divergents"] += 1
            ligne["montant_taux_divergents"] += montant
    return resume, erreurs


def check_periode_2014_2020(session, dash, categories):
    """« FESI — Période 2014-2020 », périmètre par périmètre.

    Les chiffres de référence viennent de la fusion des six sources déjà écrite
    et vérifiée en Phase 3 (`verify_pilotage_2014_2020`), pas d'une seconde
    implémentation."""
    erreurs, n = [], 0

    operations = list(operations_par_perimetre())
    engage = engage_python()
    enveloppes = enveloppes_python(engage)
    resume_cofi, erreurs_cofi = cofinancement_python(operations, categories)

    # Total et comptage d'un périmètre, dossiers sans fonds renseigné exclus des
    # deux côtés (arbitrage Phase 4, #121) : la carte KPI filtre désormais
    # `fonds IS NOT NULL`, comme le filtre Fonds de Streamlit qui les écartait
    # déjà quel que soit le fonds coché (26 dossiers Normandie, 24,6 M€).
    totaux = defaultdict(lambda: {"montant": 0.0, "count": 0})
    for op in operations:
        if op["fonds"] is None:
            continue
        cible = totaux[op["perimetre"]]
        cible["montant"] += op["montant_ue"] or 0
        cible["count"] += 1

    for perimetre in sorted(totaux):
        valeurs = {setup.DASHBOARD_2014_2020_PARAM_ID: perimetre}
        contexte = f"Période 2014-2020 ({perimetre})"
        reference = totaux[perimetre]

        montant_mb = float(scalaire(interroger(session, dash, "2014-2020 — Montant programmé total", valeurs)))
        count_mb = scalaire(interroger(session, dash, "2014-2020 — Nombre d'opérations", valeurs))
        n += 2
        if not close_enough(reference["montant"], montant_mb):
            erreurs.append(f"{contexte} / montant total : Metabase {montant_mb:,.2f} vs Streamlit {reference['montant']:,.2f}")
        if count_mb != reference["count"]:
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {count_mb} vs Streamlit {reference['count']}")

        attendu_fonds = {f: m for (p, f), m in engage.items() if p == perimetre}
        erreurs += comparer_series(
            interroger(session, dash, "2014-2020 — Montant programmé par fonds", valeurs),
            attendu_fonds, "fonds", "montant_ue", f"{contexte} / par fonds",
        )
        n += len(attendu_fonds)

        attendu_pilotage = pilotage_python(
            {f: m for (p, f), m in enveloppes.items() if p == perimetre},
            {f: m for (p, f), m in engage.items() if p == perimetre},
        )
        erreurs += comparer_pilotage(
            interroger(session, dash, "2014-2020 — Programmé vs engagé par fonds", valeurs),
            attendu_pilotage, f"{contexte} / pilotage",
        )
        n += len(attendu_pilotage)

        lignes = interroger(session, dash, "2014-2020 — Dépassements de plafond de cofinancement", valeurs)
        obtenu = {ligne["fonds"]: ligne for ligne in lignes}
        attendu_cofi = {f: v for (p, f), v in resume_cofi.items() if p == perimetre}
        for fonds, ref in attendu_cofi.items():
            ligne = obtenu.get(fonds)
            if ligne is None:
                erreurs.append(f"{contexte} / cofinancement : fonds {fonds} absent de Metabase")
                continue
            for colonne, valeur in ref.items():
                if valeur is None:
                    if ligne[colonne] is not None:
                        erreurs.append(f"{contexte} / cofinancement / {fonds} / {colonne} : Metabase {ligne[colonne]} vs Streamlit (aucun)")
                elif isinstance(valeur, str):
                    if ligne[colonne] != valeur:
                        erreurs.append(f"{contexte} / cofinancement / {fonds} / {colonne} : Metabase {ligne[colonne]} vs Streamlit {valeur}")
                elif not close_enough(valeur, ligne[colonne]):
                    erreurs.append(f"{contexte} / cofinancement / {fonds} / {colonne} : Metabase {float(ligne[colonne]):,.4f} vs Streamlit {valeur:,.4f}")
        for fonds in obtenu:
            if fonds not in attendu_cofi:
                erreurs.append(f"{contexte} / cofinancement : fonds {fonds} affiché par Metabase, absent côté Streamlit")
        n += len(attendu_cofi)

    # Verdicts de dépassement recalculés par cofinancement_python (Metabase en
    # NUMERIC vs Streamlit en flottant tolérant, #126) : un vrai bug s'ils
    # divergent depuis que le taux comparé est homogène des deux côtés (#127).
    erreurs += erreurs_cofi
    n += sum(v["n_operations"] for v in resume_cofi.values())

    return erreurs, n


def main():
    import requests

    setup.wait_for_health()
    session = requests.Session()
    session.headers["X-Metabase-Session"] = setup.get_session()

    dash = dashboards_fesi(session)
    data, programme_totals, categories = charger_references()
    agg = data["aggregates"]

    erreurs, n = [], 0

    e, c = check_vue_nationale(session, dash[setup.DASHBOARD_NAME], agg, data)
    erreurs += e
    n += c
    print(f"Vue nationale 2021-2027 : {c} valeurs comparées.")

    e, c = check_vue_regionale(session, dash[setup.REGIONAL_DASHBOARD_NAME], agg, programme_totals)
    erreurs += e
    n += c
    print(f"Vue régionale 2021-2027 : {c} valeurs comparées.")

    e, c = check_comparateur(session, dash[setup.COMPARATEUR_DASHBOARD_NAME], agg, programme_totals)
    erreurs += e
    n += c
    print(f"Comparateur 2021-2027 : {c} valeurs comparées.")

    e, c = check_volet_national(session, dash[setup.NATIONAL_DASHBOARD_NAME], agg, data, programme_totals)
    erreurs += e
    n += c
    print(f"Volet national 2021-2027 : {c} valeurs comparées.")

    e, c = check_periode_2014_2020(session, dash[setup.DASHBOARD_2014_2020_NAME], categories)
    erreurs += e
    n += c
    print(f"Période 2014-2020 : {c} valeurs comparées.")

    print(f"\n{n} valeurs comparées au total sur les cinq dashboards.")
    if erreurs:
        print(f"ÉCHEC : {len(erreurs)} écart(s) chiffré(s).")
        for erreur in erreurs:
            print(f"    - {erreur}")
        sys.exit(1)
    print("Metabase affiche les mêmes montants que le dashboard Streamlit, sur toutes les valeurs comparées.")


if __name__ == "__main__":
    main()
