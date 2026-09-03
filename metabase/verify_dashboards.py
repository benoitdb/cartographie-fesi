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
    charger,
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
from utils.periodes import (  # noqa: E402
    SEUIL_ECART_TAUX_DECLARE,
    enveloppes_ensemble_national_2014_2020,
)
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
    # `d["card_id"]` filtre les cartes virtuelles (`heading`, `text`, `link`),
    # qui portent un `card` vide : depuis #129 chaque dashboard en contient, et
    # les traverser en cherchant un nom lève un KeyError.
    dc = next(
        (d for d in dash["dashcards"] if d["card_id"] and d["card"]["name"] == nom_carte),
        None,
    )
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
        # Une liste passe telle quelle : les field filters du chantier #129 sont
        # multi-valeurs, et c'est justement la capacité qui remplace l'écran
        # Comparateur — elle doit donc être exercée ici, pas seulement supposée.
        liste = list(valeur) if isinstance(valeur, (list, tuple)) else [valeur]
        parametres.append(
            {"id": param_id, "type": param["type"], "target": mapping["target"], "value": liste}
        )

    r = session.post(
        f"{MB_URL}/api/dashboard/{dash['id']}/dashcard/{dc['id']}/card/{dc['card_id']}/query",
        json={"parameters": parametres},
    )
    r.raise_for_status()
    # 202 et non 200 : c'est le code normal de cet endpoint (la réponse peut être
    # servie en flux). Un contrôle sur `status_code == 200` conclurait « aucune
    # ligne » sur des cartes parfaitement saines.
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
    """{nom: dashboard complet} pour les cinq dashboards par usage (#129).

    Les cinq écrans des Phases 1-3 qu'ils remplacent sont archivés par
    `setup_metabase.archive_legacy()` : les chercher ici échouerait, et c'est
    voulu — ce script doit vérifier ce que l'instance montre aujourd'hui.
    """
    index = {d["name"]: d["id"] for d in session.get(f"{MB_URL}/api/dashboard").json()}
    noms = [
        setup.TERRITOIRES_NAME,
        setup.STRUCTURE_NAME,
        setup.PILOTAGE_NAME,
        setup.ANALYSES_NAME,
        setup.QUALITE_NAME,
    ]
    manquants = [n for n in noms if n not in index]
    if manquants:
        sys.exit("Dashboards absents de l'instance : " + ", ".join(manquants))
    return {n: session.get(f"{MB_URL}/api/dashboard/{index[n]}").json() for n in noms}


P_PERIODE = setup.PARAM_PERIODE
P_PERIMETRE = setup.PARAM_PERIMETRE
P_FONDS = setup.PARAM_FONDS
P2127 = "2021-2027"
P1420 = "2014-2020"


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

# --------------------------------------- 2021-2027 : engagé (Territoires, Structure)


def engage_par_region_fonds(agg, region):
    return {
        v["fonds"]: v["montant_ue_total"]
        for v in agg["by_region_fonds"].values()
        if v["region"] == region
    }


def check_engage_national(session, terr, struct, agg, data):
    """Les cartes d'engagement **sans filtre de périmètre**, période 2021-2027 :
    elles doivent rendre le total de la source, celui que lit la page d'accueil
    de Streamlit.

    C'est le contrôle qui a motivé la troisième branche de `v_engage_all` : les
    trois partitions d'`agregats.py` (mono-région, interrégional, national) sont
    exclusives, et il en manquait une — 13 opérations, 1,625 M€, soit 0,02 %.
    Assez peu pour passer inaperçu à l'oeil, assez pour faire mentir un KPI.
    """
    erreurs, n = [], 0
    by_fonds, by_region = agg["by_fonds"], agg["by_region"]

    for fonds in [None, *sorted(by_fonds)]:
        valeurs = {P_PERIODE: P2127, P_FONDS: fonds}
        selection = sorted(by_fonds) if fonds is None else [fonds]
        libelle = "tous fonds" if fonds is None else f"fonds={fonds}"
        contexte = f"Engagé 2021-2027 ({libelle})"

        attendu_count = sum(by_fonds[f]["count"] for f in selection)
        attendu_montant = sum(by_fonds[f]["montant_ue_total"] for f in selection)

        obtenu = scalaire(interroger(session, terr, "Engagé — Montant UE", valeurs))
        if not close_enough(attendu_montant, obtenu):
            erreurs.append(f"{contexte} / montant UE : Metabase {float(obtenu):,.2f} vs Streamlit {attendu_montant:,.2f}")
        obtenu = scalaire(interroger(session, terr, "Engagé — Nombre d'opérations", valeurs))
        if not close_enough(attendu_count, obtenu):
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {obtenu} vs Streamlit {attendu_count}")
        n += 2

        # La même carte, sur l'autre dashboard : c'est tout l'intérêt de la
        # convention de paramètre unique, et la seule façon de vérifier que le
        # câblage a bien été refait des deux côtés.
        obtenu = scalaire(interroger(session, struct, "Engagé — Montant UE", valeurs))
        if not close_enough(attendu_montant, obtenu):
            erreurs.append(f"{contexte} / montant UE (Structure) : Metabase {float(obtenu):,.2f} vs Streamlit {attendu_montant:,.2f}")
        n += 1

        erreurs += comparer_series(
            interroger(session, struct, "Engagé — Par fonds", valeurs),
            {f: by_fonds[f]["montant_ue_total"] for f in selection},
            "fonds", "montant_ue", f"{contexte} / par fonds",
        )
        n += len(selection)

        # La choroplèthe n'affiche que les périmètres géographiques : `national`
        # et `interregional` en sont écartés par le SQL, pas par le fond de
        # carte, qui les laisserait tomber sans le dire.
        if fonds is None:
            attendu_regions = {r: v["montant_ue_total"] for r, v in by_region.items()}
        else:
            attendu_regions = {
                v["region"]: v["montant_ue_total"]
                for v in agg["by_region_fonds"].values()
                if v["fonds"] == fonds
            }
        erreurs += comparer_series(
            interroger(session, terr, "Engagé — Carte des régions", valeurs),
            attendu_regions, "region", "montant_ue", f"{contexte} / carte",
        )
        n += len(attendu_regions)

        # Le classement par périmètre, lui, porte les trois partitions. Volet
        # national et interrégional se recalculent par fonds sur les opérations :
        # `aggregates` ne les décompose pas (il n'en donne que le total), et tous
        # les fonds n'y sont pas représentés — FTJ n'a ni ligne nationale ni
        # ligne interrégionale, et une entrée à zéro ferait échouer la
        # comparaison dans l'autre sens.
        attendu_perimetres = dict(attendu_regions)
        hors_region = defaultdict(float)
        for op in data["operations"]:
            if not op.get(FONDS) or (fonds is not None and op[FONDS] != fonds):
                continue
            if op.get("is_national"):
                hors_region["national"] += op[MONTANT] or 0
            elif op.get("is_interregional"):
                hors_region["interregional"] += op[MONTANT] or 0
        attendu_perimetres.update(hors_region)
        erreurs += comparer_series(
            interroger(session, terr, "Engagé — Par périmètre", valeurs),
            attendu_perimetres, "perimetre", "montant_ue", f"{contexte} / par périmètre",
        )
        n += len(attendu_perimetres)

    return erreurs, n


def check_engage_perimetres(session, terr, agg, data):
    """Le paramètre `Périmètre`, périmètre par périmètre, puis **par paires**.

    Les paires sont le coeur du chantier : c'est ce qui remplace l'écran
    Comparateur. Un field filter mono-valeur répondrait sans erreur sur la
    première valeur seulement — un demi-résultat parfaitement plausible.
    """
    erreurs, n = [], 0
    by_region = agg["by_region"]

    def kpi(perimetre, montant_ref, count_ref, contexte):
        nonlocal erreurs, n
        valeurs = {P_PERIODE: P2127, P_PERIMETRE: perimetre}
        obtenu = scalaire(interroger(session, terr, "Engagé — Montant UE", valeurs))
        if not close_enough(montant_ref, obtenu):
            erreurs.append(f"{contexte} / montant UE : Metabase {float(obtenu):,.2f} vs Streamlit {montant_ref:,.2f}")
        obtenu = scalaire(interroger(session, terr, "Engagé — Nombre d'opérations", valeurs))
        if not close_enough(count_ref, obtenu):
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {obtenu} vs Streamlit {count_ref}")
        n += 2

    for region in sorted(by_region):
        contexte = f"Engagé 2021-2027 ({region})"
        kpi(region, by_region[region]["montant_ue_total"], by_region[region]["count"], contexte)
        engage_region = engage_par_region_fonds(agg, region)
        erreurs += comparer_series(
            interroger(session, terr, "Engagé — Par fonds", {P_PERIODE: P2127, P_PERIMETRE: region}),
            engage_region, "fonds", "montant_ue", f"{contexte} / par fonds",
        )
        n += len(engage_region)

    # Volet national et interrégional : deux périmètres à part entière du même
    # paramètre, là où les Phases 1-3 leur consacraient un écran ou rien du tout.
    kpi("national", agg["national"]["montant_ue_total"], agg["national"]["count"],
        "Engagé 2021-2027 (national)")
    kpi("interregional", agg["interregional"]["montant_ue_total"], agg["interregional"]["count"],
        "Engagé 2021-2027 (interrégional)")

    engage_national = defaultdict(float)
    for op in data["operations"]:
        if op.get("is_national") and op.get(FONDS):
            engage_national[op[FONDS]] += op[MONTANT] or 0
    erreurs += comparer_series(
        interroger(session, terr, "Engagé — Par fonds", {P_PERIODE: P2127, P_PERIMETRE: "national"}),
        dict(engage_national), "fonds", "montant_ue", "Engagé 2021-2027 (national) / par fonds",
    )
    n += len(engage_national)

    # Les paires reprennent celles que testait le Comparateur, dont le cas #62
    # (Auvergne-Rhône-Alpes, dépassement FSE+) et un DROM.
    paires = [
        ("Bretagne", "Occitanie"),
        ("Auvergne-Rhône-Alpes", "La Réunion"),
        ("Île-de-France", "Corse"),
        ("Bretagne", "national"),
    ]
    for a, b in paires:
        contexte = f"Engagé 2021-2027 ({a} + {b})"
        totaux = {
            r: (agg["national"] if r == "national" else by_region[r])
            for r in (a, b)
        }
        kpi([a, b], sum(v["montant_ue_total"] for v in totaux.values()),
            sum(v["count"] for v in totaux.values()), contexte)

        lignes = interroger(session, terr, "Engagé — Par périmètre",
                            {P_PERIODE: P2127, P_PERIMETRE: [a, b]})
        erreurs += comparer_series(
            lignes, {r: v["montant_ue_total"] for r, v in totaux.items()},
            "perimetre", "montant_ue", f"{contexte} / par périmètre",
        )
        n += 2

    # Un triplet, pour que « plusieurs » ne veuille pas dire « exactement deux ».
    trois = ["Bretagne", "Occitanie", "Normandie"]
    lignes = interroger(session, terr, "Engagé — Par périmètre",
                        {P_PERIODE: P2127, P_PERIMETRE: trois})
    erreurs += comparer_series(
        lignes, {r: by_region[r]["montant_ue_total"] for r in trois},
        "perimetre", "montant_ue", "Engagé 2021-2027 (trois régions) / par périmètre",
    )
    n += 3

    return erreurs, n


def check_pilotage_2021_2027(session, pil, agg, programme_totals, data):
    """Programmé vs engagé sur le dashboard Pilotage, périmètre par périmètre,
    plus le classement des taux et la trajectoire."""
    erreurs, n = [], 0
    by_region = agg["by_region"]

    engage_par_perimetre = {r: engage_par_region_fonds(agg, r) for r in by_region}
    engage_national = defaultdict(float)
    for op in data["operations"]:
        if op.get("is_national") and op.get(FONDS):
            engage_national[op[FONDS]] += op[MONTANT] or 0
    engage_par_perimetre["national"] = dict(engage_national)

    for perimetre in [*sorted(by_region), "national"]:
        valeurs = {P_PERIODE: P2127, P_PERIMETRE: perimetre}
        contexte = f"Pilotage 2021-2027 ({perimetre})"
        attendu = pilotage_python(
            programme_totals.get(perimetre, {}), engage_par_perimetre[perimetre]
        )
        erreurs += comparer_pilotage(
            interroger(session, pil, "Pilotage — Programmé vs engagé par fonds", valeurs),
            attendu, contexte,
        )
        n += len(attendu)

        # La table de détail lit la vue sans rien recalculer : elle doit dire
        # exactement la même chose que le graphique posé au-dessus d'elle.
        detail = {
            ligne["fonds"]: ligne
            for ligne in interroger(session, pil, "Pilotage — Détail par périmètre et fonds", valeurs)
        }
        for fonds, ref in attendu.items():
            ligne = detail.get(fonds)
            if ligne is None:
                erreurs.append(f"{contexte} / détail : fonds {fonds} absent")
                continue
            for colonne, valeur in ref.items():
                if not close_enough(valeur, ligne[colonne]):
                    erreurs.append(
                        f"{contexte} / détail / {fonds} / {colonne} : "
                        f"Metabase {float(ligne[colonne]):,.4f} vs Streamlit {valeur:,.4f}"
                    )
        n += len(attendu)

    # Classement des taux : la carte ignore volontairement le filtre Périmètre
    # (elle sert à situer un périmètre parmi tous les autres), donc elle doit
    # rendre TOUS les périmètres programmés, quoi qu'on lui demande.
    attendu_taux = {}
    for perimetre, engage in engage_par_perimetre.items():
        lignes = pilotage_python(programme_totals.get(perimetre, {}), engage)
        programme = sum(v["programme"] for v in lignes.values())
        engage_total = sum(v["engage"] for v in lignes.values())
        if programme > 0:
            attendu_taux[perimetre] = taux_consommation(engage_total, programme)
    erreurs += comparer_series(
        interroger(session, pil, "Pilotage — Taux de consommation par périmètre",
                   {P_PERIODE: P2127}),
        attendu_taux, "perimetre", "taux", "Pilotage 2021-2027 / taux par périmètre",
    )
    n += len(attendu_taux)

    # Trajectoire : le dernier point de la courbe est le cumul total. Alignée sur
    # `build_trajectoire` (#121, Phase 4) — date de DÉBUT d'opération, pas date
    # de convention ; l'écart entre les deux courbes valait 2 324 M€ au dernier
    # point. La carte ignore le filtre Période, elle est scopée 2021-2027 en dur.
    for fonds in [None, *sorted(agg["by_fonds"])]:
        libelle = "tous fonds" if fonds is None else f"fonds={fonds}"
        lignes = interroger(session, pil, "Pilotage — Engagement cumulé 2021-2027", {P_FONDS: fonds})
        cumul_mb = float(lignes[-1]["montant_cumule"]) if lignes else 0
        cumul_ref = sum(
            op[MONTANT] or 0
            for op in data["operations"]
            if (fonds is None or op.get(FONDS) == fonds) and load_data.parse_date(op.get(DATE_DEBUT))
        )
        if not close_enough(cumul_ref, cumul_mb):
            erreurs.append(
                f"Pilotage 2021-2027 ({libelle}) / engagement cumulé : "
                f"Metabase {cumul_mb:,.2f} vs Streamlit {cumul_ref:,.2f}"
            )
        n += 1

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


def _comparer_cofinancement(lignes, attendu, contexte, erreurs):
    """Compare les lignes de la carte cofinancement à `resume_cofi`, clé
    (région, fonds). Les colonnes sont hétérogènes — catégorie de cohésion en
    texte, plafonds parfois absents, comptages et montants — d'où les trois cas."""
    obtenu = {(ligne["region"], ligne["fonds"]): ligne for ligne in lignes}
    for cle, ref in attendu.items():
        ligne = obtenu.get(cle)
        if ligne is None:
            erreurs.append(f"{contexte} : {cle} absent de Metabase")
            continue
        for colonne, valeur in ref.items():
            if valeur is None:
                if ligne[colonne] is not None:
                    erreurs.append(f"{contexte} / {cle} / {colonne} : Metabase {ligne[colonne]} vs Streamlit (aucun)")
            elif isinstance(valeur, str):
                if ligne[colonne] != valeur:
                    erreurs.append(f"{contexte} / {cle} / {colonne} : Metabase {ligne[colonne]} vs Streamlit {valeur}")
            elif not close_enough(valeur, ligne[colonne]):
                erreurs.append(f"{contexte} / {cle} / {colonne} : Metabase {float(ligne[colonne]):,.4f} vs Streamlit {valeur:,.4f}")
    for cle in obtenu:
        if cle not in attendu:
            erreurs.append(f"{contexte} : {cle} affiché par Metabase, absent côté Streamlit")


def check_periode_2014_2020(session, terr, pil, analyses, categories):
    """La période close, vue **par le paramètre Période** et non par un écran.

    Les chiffres de référence viennent de la fusion des six sources déjà écrite
    et vérifiée en Phase 3 (`verify_pilotage_2014_2020`), pas d'une seconde
    implémentation. Deux différences avec l'écran qu'elle remplace :

    - la valeur sentinelle `perimetre = 'Ensemble national'` disparaît. Elle
      existait parce qu'un template-tag texte était **obligatoire** et
      mono-valeur : il fallait une valeur qui veuille dire « ne filtre pas ».
      Un field filter non requis sans valeur ne filtre pas, tout simplement ;
    - le total « sans filtre » couvre donc les mêmes lignes qu'elle, et c'est
      vérifié ici sur les mêmes références.
    """
    erreurs, n = [], 0

    operations = list(operations_par_perimetre())
    engage = engage_python()
    enveloppes = enveloppes_python(engage)
    resume_cofi, erreurs_cofi = cofinancement_python(operations, categories)

    # Dossiers sans fonds renseigné exclus des deux côtés (arbitrage Phase 4,
    # #121) : `v_engage_2014_2020` filtre `fonds IS NOT NULL`, comme le filtre
    # Fonds de Streamlit qui les écartait déjà quel que soit le fonds coché
    # (26 dossiers Normandie, 24,6 M€).
    totaux = defaultdict(lambda: {"montant": 0.0, "count": 0})
    for op in operations:
        if op["fonds"] is None:
            continue
        cible = totaux[op["perimetre"]]
        cible["montant"] += op["montant_ue"] or 0
        cible["count"] += 1

    for perimetre in sorted(totaux):
        valeurs = {P_PERIODE: P1420, P_PERIMETRE: perimetre}
        contexte = f"Période 2014-2020 ({perimetre})"
        reference = totaux[perimetre]

        montant_mb = float(scalaire(interroger(session, terr, "Engagé — Montant UE", valeurs)))
        count_mb = scalaire(interroger(session, terr, "Engagé — Nombre d'opérations", valeurs))
        n += 2
        if not close_enough(reference["montant"], montant_mb):
            erreurs.append(f"{contexte} / montant : Metabase {montant_mb:,.2f} vs Streamlit {reference['montant']:,.2f}")
        if count_mb != reference["count"]:
            erreurs.append(f"{contexte} / nombre d'opérations : Metabase {count_mb} vs Streamlit {reference['count']}")

        attendu_fonds = {f: m for (p, f), m in engage.items() if p == perimetre}
        erreurs += comparer_series(
            interroger(session, terr, "Engagé — Par fonds", valeurs),
            attendu_fonds, "fonds", "montant_ue", f"{contexte} / par fonds",
        )
        n += len(attendu_fonds)

        attendu_pilotage = pilotage_python(
            {f: m for (p, f), m in enveloppes.items() if p == perimetre},
            {f: m for (p, f), m in engage.items() if p == perimetre},
        )
        erreurs += comparer_pilotage(
            interroger(session, pil, "Pilotage — Programmé vs engagé par fonds", valeurs),
            attendu_pilotage, f"{contexte} / pilotage",
        )
        n += len(attendu_pilotage)

        attendu_cofi = {(p, f): v for (p, f), v in resume_cofi.items() if p == perimetre}
        _comparer_cofinancement(
            interroger(session, analyses,
                       "Contrôle — Dépassements de plafond de cofinancement (2014-2020)",
                       {P_PERIMETRE: perimetre}),
            attendu_cofi, f"{contexte} / cofinancement", erreurs,
        )
        n += len(attendu_cofi)

    # Sans filtre de périmètre : ce que l'ancienne sentinelle « Ensemble national »
    # produisait, obtenu en ne cochant rien.
    valeurs = {P_PERIODE: P1420}
    contexte = "Période 2014-2020 (tous périmètres)"
    montant_ensemble = sum(v["montant"] for v in totaux.values())
    count_ensemble = sum(v["count"] for v in totaux.values())

    montant_mb = float(scalaire(interroger(session, terr, "Engagé — Montant UE", valeurs)))
    count_mb = scalaire(interroger(session, terr, "Engagé — Nombre d'opérations", valeurs))
    n += 2
    if not close_enough(montant_ensemble, montant_mb):
        erreurs.append(f"{contexte} / montant : Metabase {montant_mb:,.2f} vs Streamlit {montant_ensemble:,.2f}")
    if count_mb != count_ensemble:
        erreurs.append(f"{contexte} / nombre d'opérations : Metabase {count_mb} vs Streamlit {count_ensemble}")

    engage_ensemble = defaultdict(float)
    for (_, fonds), montant in engage.items():
        engage_ensemble[fonds] += montant
    engage_ensemble = dict(engage_ensemble)
    erreurs += comparer_series(
        interroger(session, terr, "Engagé — Par fonds", valeurs),
        engage_ensemble, "fonds", "montant_ue", f"{contexte} / par fonds",
    )
    n += len(engage_ensemble)

    fonds_engages_par_perimetre = defaultdict(set)
    for perimetre, fonds in engage:
        fonds_engages_par_perimetre[perimetre].add(fonds)
    totaux_enveloppes = charger("programme_totals_2014_2020.json")
    enveloppes_ensemble, _ = enveloppes_ensemble_national_2014_2020(
        fonds_engages_par_perimetre, totaux_enveloppes
    )
    erreurs += comparer_pilotage(
        interroger(session, pil, "Pilotage — Programmé vs engagé par fonds", valeurs),
        pilotage_python(enveloppes_ensemble, engage_ensemble), f"{contexte} / pilotage",
    )
    n += len(enveloppes_ensemble)

    # Cofinancement sans filtre : toutes les régions à la fois. L'ancienne carte
    # restait vide sur « Ensemble national » parce qu'un plafond n'est opposable
    # qu'à la maille d'une région — la nouvelle ne prétend toujours pas agréger,
    # elle liste région par région.
    _comparer_cofinancement(
        interroger(session, analyses,
                   "Contrôle — Dépassements de plafond de cofinancement (2014-2020)"),
        resume_cofi, f"{contexte} / cofinancement", erreurs,
    )
    n += len(resume_cofi)

    # Verdicts de dépassement recalculés par cofinancement_python (Metabase en
    # NUMERIC vs Streamlit en flottant tolérant, #126).
    erreurs += erreurs_cofi
    n += sum(v["n_operations"] for v in resume_cofi.values())

    return erreurs, n


def check_qualite_sources(session, qual, agg):
    """Le tableau de chargement par source. Il ne se somme pas (les six sources
    2014-2020 se chevauchent) : ce qui se vérifie, c'est chaque ligne prise
    isolément. Seule 2021-2027 a une référence Streamlit — une source unique,
    donc le total de la période."""
    erreurs, n = [], 0
    lignes = interroger(session, qual, "Sources — Opérations chargées par source", {P_PERIODE: P2127})
    if len(lignes) != 1:
        erreurs.append(f"Qualité des sources : {len(lignes)} source(s) pour 2021-2027, attendu 1")
        return erreurs, n

    ligne = lignes[0]
    attendu_count = sum(v["count"] for v in agg["by_fonds"].values())
    attendu_montant = sum(v["montant_ue_total"] for v in agg["by_fonds"].values())
    if ligne["n_operations"] != attendu_count:
        erreurs.append(f"Qualité des sources / opérations : Metabase {ligne['n_operations']} vs Streamlit {attendu_count}")
    if not close_enough(attendu_montant, ligne["montant_ue"]):
        erreurs.append(f"Qualité des sources / montant : Metabase {float(ligne['montant_ue']):,.2f} vs Streamlit {attendu_montant:,.2f}")
    if ligne["sans_fonds"] != 0:
        erreurs.append(f"Qualité des sources / sans_fonds : Metabase {ligne['sans_fonds']}, attendu 0 sur 2021-2027")
    n += 3
    return erreurs, n


def main():
    import requests

    setup.wait_for_health()
    session = requests.Session()
    session.headers["X-Metabase-Session"] = setup.get_session()

    dash = dashboards_fesi(session)
    terr = dash[setup.TERRITOIRES_NAME]
    struct = dash[setup.STRUCTURE_NAME]
    pil = dash[setup.PILOTAGE_NAME]
    analyses = dash[setup.ANALYSES_NAME]
    qual = dash[setup.QUALITE_NAME]

    data, programme_totals, categories = charger_references()
    agg = data["aggregates"]

    # Appels séquentiels et non une liste de tuples : chaque section imprime son
    # compte dès qu'elle a fini. Une liste construite d'un bloc lancerait les
    # cinq séries de requêtes avant la première ligne de sortie — plusieurs
    # minutes de silence.
    erreurs, n = [], 0

    def section(libelle, resultat):
        nonlocal erreurs, n
        e, c = resultat
        erreurs += e
        n += c
        print(f"{libelle} : {c} valeurs comparées.")

    section("Engagé 2021-2027, sans filtre de périmètre",
            check_engage_national(session, terr, struct, agg, data))
    section("Engagé 2021-2027, par périmètre et par paires",
            check_engage_perimetres(session, terr, agg, data))
    section("Pilotage 2021-2027",
            check_pilotage_2021_2027(session, pil, agg, programme_totals, data))
    section("Période 2014-2020",
            check_periode_2014_2020(session, terr, pil, analyses, categories))
    section("Qualité des sources",
            check_qualite_sources(session, qual, agg))

    print(f"\n{n} valeurs comparées au total sur les cinq dashboards par usage.")
    if erreurs:
        print(f"ÉCHEC : {len(erreurs)} écart(s) chiffré(s).")
        for erreur in erreurs:
            print(f"    - {erreur}")
        sys.exit(1)
    print("Metabase affiche les mêmes montants que le dashboard Streamlit, sur toutes les valeurs comparées.")


if __name__ == "__main__":
    main()
