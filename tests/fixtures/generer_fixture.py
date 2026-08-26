"""Régénère la fixture de test du dashboard à partir des données réelles du poste.

À relancer quand le schéma de `data.json` change (nouvelle colonne, colonne
renommée) — sinon les tests de fumée valideraient un schéma périmé.

    cd "Cartographie FESI" && venv/bin/python tests/fixtures/generer_fixture.py

Ce que la fixture contient, et pourquoi (voir aussi README.md à côté) :

- un échantillon **stratifié par région** des opérations, pour que les 19 régions
  et les 3 fonds soient représentés — un tirage aléatoire simple laisserait des
  pages sans données et le test de fumée ne prouverait plus rien pour elles ;
- **toutes les opérations interrégionales** (13 sur 16 625) : trop rares pour
  survivre à un échantillonnage par région, mais le dashboard lit
  `aggregates["interregional"]` sans valeur par défaut — un échantillon qui n'en
  contiendrait aucune produirait des agrégats sans cette clé, et les pages
  échoueraient sur la fixture alors qu'elles fonctionnent sur les vraies données ;
- le champ `Objectifs et réalisations escomptés et effectifs` **tronqué** : il
  pèse 61,5 % du fichier réel et n'est lu nulle part dans `dashboard/`. Il est
  conservé (tronqué) plutôt que supprimé, pour que le schéma reste fidèle ;
- un bloc `aggregates` **recalculé sur l'échantillon**, et non repris du fichier
  complet. Il décrivait jusqu'ici les 16 625 opérations réelles, ce qui interdisait
  toute assertion sur une valeur (issue #60, levée par l'extraction
  d'`agregats.calculer_agregats`).

**Une fixture par période** (issue #83) : `data.json` (2021-2027) et
`data_2014-2020.json`. Les deux fichiers n'ont ni les mêmes colonnes ni les mêmes
fonds, et la page 2014-2020 ne se rendrait pas sur un échantillon de l'autre
période. Le champ volumineux à tronquer et le schéma de colonnes diffèrent donc
par période — d'où `PERIODES` plus bas plutôt qu'un chemin en dur.

**Trois fixtures de plus depuis #95**, pour les fichiers régionaux hors-Synergie lus
directement par la page 2014-2020 (Normandie, Nouvelle-Aquitaine, Bretagne — #68, #95) :
`data_2014-2020_normandie.json`, `data_2014-2020_nouvelle_aquitaine.json` et
`data_2014-2020_bretagne_officiel.json`. Un seul périmètre par fichier, donc pas
d'échantillonnage stratifié par région comme pour `echantillonner` — voir
`generer_hors_synergie`, qui prend des tranches ciblées pour couvrir chaque fonds (et,
pour Normandie, les opérations à fonds vide, cf. #95).
"""

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent.parent
SOURCE = RACINE / "data" / "processed"
CIBLE = Path(__file__).resolve().parent / "dashboard"

# Même raison que dans tests/conftest.py : le dossier porte un tiret, ses scripts
# s'importent à plat.
sys.path.insert(0, str(RACINE / "data-pipeline"))

from agregats import calculer_agregats, partitionner  # noqa: E402
from schema_source import SCHEMAS, build_cols  # noqa: E402

# Assez pour que chaque région ait de quoi remplir ses graphiques, assez peu pour
# que la fixture reste sous le mégaoctet.
OPS_PAR_REGION = 20
LONGUEUR_MAX = 200

# Une entrée par période : fichier source, schéma de colonnes à repasser à
# `build_cols`, et champ de texte libre à tronquer (il pèse l'essentiel du
# fichier et n'est lu nulle part dans `dashboard/`).
PERIODES = {
    "2021-2027": {
        "fichier": "data.json",
        "schema": SCHEMAS["2021-2027"],
        "champ_volumineux": "Objectifs et réalisations escomptés et effectifs",
    },
    "2014-2020": {
        "fichier": "data_2014-2020.json",
        "schema": SCHEMAS["2014-2020"],
        "champ_volumineux": "Résumé de l'opération",
    },
}

# Petits fichiers lus par le dashboard mais gitignorés : copiés intégralement.
COPIES_INTEGRALES = ["beneficiaires_fuzzy.json", "transferts_solidarite.json"]

# Fichiers régionaux hors-Synergie (#68, #95) : un seul périmètre chacun, donc pas de
# stratification par région. `tranches` désigne des plages `[début, fin)` de l'ordre du
# fichier source, choisies pour couvrir chaque fonds (et, pour Normandie, des dossiers à
# fonds vide) — voir `generer_hors_synergie`.
SOURCES_HORS_SYNERGIE = {
    "2014-2020-normandie": {
        "fichier": "data_2014-2020_normandie.json",
        "schema": SCHEMAS["2014-2020-normandie"],
        # FEDER (0), FSE (28) ; FEDER REACT-EU (499) ; IEJ (557) ; fonds vide (1152).
        "tranches": [(0, 40), (499, 509), (557, 567), (1152, 1157)],
    },
    "2014-2020-nouvelle-aquitaine": {
        "fichier": "data_2014-2020_nouvelle_aquitaine.json",
        "schema": SCHEMAS["2014-2020-nouvelle-aquitaine"],
        # FEDER (0), FSE (6), IEJ (23) : les trois tiennent dans les 40 premières lignes.
        "tranches": [(0, 40)],
    },
    "2014-2020-bretagne-officiel": {
        "fichier": "data_2014-2020_bretagne_officiel.json",
        "schema": SCHEMAS["2014-2020-bretagne-officiel"],
        # FEDER (0) ; les 7 lignes FSE sont dispersées (342, 364, 570, 683, 684, 810,
        # 849) : des tranches ciblées les couvrent toutes plutôt qu'un seul bloc.
        "tranches": [(0, 10), (340, 370), (680, 690), (845, 852)],
    },
    # Un seul fichier mais sept programmes à router (issue #95, point 3) : une tranche par
    # `Libellé_po` plutôt qu'un seul bloc, pour que chacun des cinq PO DROM et des deux
    # programmes nationaux (PON FSE, PO IEJ) survive à l'échantillonnage. Index de première
    # apparition de chaque programme dans le fichier réel, relevés une fois : PON FSE (0),
    # PO IEJ (441), PO Guadeloupe (8013), PO Guyane (8376), PO Martinique (14365),
    # PO Mayotte (14537), PO réunion (21961).
    "2014-2020-pon-fse": {
        "fichier": "data_2014-2020_pon_fse.json",
        "schema": SCHEMAS["2014-2020-pon-fse"],
        "tranches": [
            (0, 10),
            (441, 451),
            (8013, 8023),
            (8376, 8386),
            (14365, 14375),
            (14537, 14547),
            (21961, 21971),
        ],
    },
}


def region_de(op):
    regions = op.get("regions_modernes") or []
    return regions[0] if regions else "(sans région)"


def tronquer_champ_volumineux(op, champ):
    op = dict(op)
    texte = op.get(champ)
    if isinstance(texte, str) and len(texte) > LONGUEUR_MAX:
        op[champ] = texte[:LONGUEUR_MAX] + "…"
    return op


def echantillonner(operations, champ_volumineux):
    """Opérations retenues : les `OPS_PAR_REGION` premières de chaque région, plus
    toutes les interrégionales (cf. docstring du module). L'ordre du fichier
    source est conservé, pour que deux régénérations donnent le même résultat."""
    par_region = defaultdict(list)
    for op in operations:
        par_region[region_de(op)].append(op)

    retenus = {}
    for region in sorted(par_region):
        for op in par_region[region][:OPS_PAR_REGION]:
            retenus[op["Numéro Opération"]] = op
    for op in operations:
        if op.get("is_interregional"):
            retenus[op["Numéro Opération"]] = op

    ordre = {op["Numéro Opération"]: rang for rang, op in enumerate(operations)}
    return [
        tronquer_champ_volumineux(op, champ_volumineux)
        for op in sorted(retenus.values(), key=lambda o: ordre[o["Numéro Opération"]])
    ]


def recalculer(echantillon, metadata_source, schema):
    """Agrégats et métadonnées de l'échantillon, par le même code que le pipeline.

    Le DataFrame est reconstruit depuis les enregistrements JSON : leurs clés sont
    les libellés réels des colonnes, dans l'ordre du fichier source, donc
    `build_cols` retrouve le mapping comme au moment de l'ingestion."""
    df = pd.DataFrame(echantillon)
    cols = build_cols(df.columns, schema=schema)
    partitions = partitionner(df)
    agregats = calculer_agregats(df, cols, partitions)

    metadata = dict(metadata_source)
    metadata.update(
        total_operations=len(df),
        nb_regions_harmonized=len(agregats["by_region"]),
        nb_regions_raw=int(df[cols["region"]].nunique()),
        nb_fonds=int(df[cols["fonds"]].nunique()),
        partitions={
            "mono_region": len(partitions.mono_region),
            "interregional": len(partitions.interregional),
            "national": len(partitions.national),
        },
        fixture=(
            f"Échantillon de test : {len(df)} opérations stratifiées par région, "
            "toutes les interrégionales incluses. Le bloc 'aggregates' et ce bloc "
            "'metadata' sont recalculés sur cet échantillon, pas repris du jeu complet."
        ),
    )
    # La dimension thématique n'existe pas dans toutes les périodes : sa clé reste
    # **absente** du metadata quand elle l'est du schéma, comme ses blocs le sont
    # des agrégats (cf. agregats.py) — un zéro se lirait comme une dimension
    # mesurée et vide.
    if "objectif_strat" in cols:
        metadata["nb_objectifs_strategiques"] = int(df[cols["objectif_strat"]].nunique())
    return agregats, metadata


def generer(periode, config):
    """Écrit la fixture d'une période et renvoie son bloc metadata."""
    data = json.loads((SOURCE / config["fichier"]).read_text(encoding="utf-8"))

    echantillon = echantillonner(data["operations"], config["champ_volumineux"])
    agregats, metadata = recalculer(echantillon, data["metadata"], config["schema"])

    # allow_nan=False : un NaN résiduel produirait un JSON que les parseurs
    # stricts refusent, et surtout une valeur qui ne veut rien dire dans un
    # agrégat. Mieux vaut échouer ici qu'écrire la fixture.
    (CIBLE / config["fichier"]).write_text(
        json.dumps(
            {"metadata": metadata, "operations": echantillon, "aggregates": agregats},
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(
        f"{periode} : {len(echantillon)} opérations · "
        f"{metadata['nb_regions_harmonized']} régions · partitions {metadata['partitions']}"
    )
    return metadata


def generer_hors_synergie(source, config):
    """Écrit la fixture d'un fichier régional hors-Synergie (#68, #95), ou ne fait rien
    s'il est absent du poste (gitignoré, non régénérable sans le fichier XLSX/XLS source
    correspondant) — la fixture existante, si elle est déjà committée, n'est alors pas
    écrasée par un échantillon appauvri."""
    chemin = SOURCE / config["fichier"]
    if not chemin.exists():
        print(f"{source} : fichier absent ({chemin}), fixture non régénérée")
        return

    data = json.loads(chemin.read_text(encoding="utf-8"))
    operations = data["operations"]

    echantillon = []
    vus = set()
    for debut, fin in config["tranches"]:
        for op in operations[debut:fin]:
            cle = id(op)
            if cle not in vus:
                vus.add(cle)
                echantillon.append(op)

    agregats, metadata = recalculer(echantillon, data["metadata"], config["schema"])
    (CIBLE / config["fichier"]).write_text(
        json.dumps(
            {"metadata": metadata, "operations": echantillon, "aggregates": agregats},
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(
        f"{source} : {len(echantillon)} opérations · "
        f"{metadata['nb_regions_harmonized']} région(s) · partitions {metadata['partitions']}"
    )


def main():
    CIBLE.mkdir(parents=True, exist_ok=True)

    for periode, config in PERIODES.items():
        generer(periode, config)

    for source, config in SOURCES_HORS_SYNERGIE.items():
        generer_hors_synergie(source, config)

    for nom in COPIES_INTEGRALES:
        shutil.copy(SOURCE / nom, CIBLE / nom)

    for chemin in sorted(CIBLE.glob("*.json")):
        print(f"  {chemin.stat().st_size // 1024:>5} Ko  {chemin.name}")


if __name__ == "__main__":
    main()
