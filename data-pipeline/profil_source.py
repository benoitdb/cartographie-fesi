"""Génère le profil JSON d'une source d'opérations, une par fichier.

Lit un XLSX brut de `data/raw/`, appelle `profiler_source`, et écrit
`data/processed/profil_<source>.json`. Idempotent, rejouable à chaque nouveau
millésime. Le JSON est committé (comme `programme_totals.json`) pour que la page
« Validation de la source » du dashboard tourne sans le XLSX brut.

La clé est la **source** (un fichier), pas la période : une même période peut
avoir plusieurs fichiers (2014-2020 a le fichier Synergie national, le fichier
*programmées*, et à terme les fichiers hors-Synergie régionaux — issue #68), qui
donnent chacun leur rapport. Ajouter une source, c'est ajouter une entrée à
`SOURCES` et relancer — le dashboard la découvre par glob.

Usage :
    python profil_source.py                       # défaut : 2014-2020-synergie
    python profil_source.py 2014-2020-synergie
    python profil_source.py 2021-2027-conventionnees
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from profilage_source import profiler_source
from region_mapping import PROGRAMME_TO_REGION, indexer_programmes, region_du_programme
from schema_source import build_cols, millesime_du_fichier

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"

# Mapping programme → région moderne pour 2014-2020 (issue #12 : la colonne
# `Région de l'opération` n'est remplie qu'à 16 %, mais le libellé du programme
# porte la région dans la quasi-totalité des cas). Régions modernes post-2016,
# cohérentes avec `region_mapping.MODERN_REGIONS`. Les programmes **nationaux**
# (FEAD, PNAT Europ'Act) et **interrégionaux** (Massif Central, Loire, Massif des
# Alpes, Rhône-Saône, Pyrénées) n'ont pas de région unique → `None`, ce n'est
# pas un trou de mapping. À consolider dans `region_mapping` quand #12 câblera
# l'ingestion 2014-2020.
PROGRAMME_TO_REGION_2014_2020 = {
    "Programme opérationnel FEDER-FSE Centre-Val de Loire 2014-2020": "Centre-Val de Loire",
    "Programme opérationnel FEDER Réunion Conseil Régional 2014-2020": "La Réunion",
    "Programme Opérationnel Feder FSE Lorraine et massif des Vosges 2014-2020": "Grand Est",
    "Programme Opérationnel FEDER-FSE Languedoc-Roussillon 2014-2020": "Occitanie",
    "Programme Opérationnel FEDER-FSE Bourgogne 2014- 2020": "Bourgogne-Franche-Comté",
    "Programme opérationnel FEDER-FSE Midi-Pyrénées et Garonne 2014-2020": "Occitanie",
    "Programme opérationnel régional Auvergne FEDER-FSE 2014-2020": "Auvergne-Rhône-Alpes",
    "Programme Opérationnel FEDER-FSE Nord-Pas de Calais 2014-2020": "Hauts-de-France",
    "Programme opérationnel FEDER-FSE Ile-de-France et Bassin de Seine 2014-2020": "Île-de-France",
    "Programme opérationnel FEDER FSE IEJ Champagne Ardenne 2014-2020": "Grand Est",
    "Programme opérationnel FEDER-FSE Guadeloupe Conseil Régional 2014-2020": "Guadeloupe",
    "Programme opérationnel FEDER-FSE Martinique Conseil Régional 2014-2020": "Martinique",
    "Programme opérationnel FEDER-FSE Picardie 2014-2020": "Hauts-de-France",
    "Programme opérationnel FEDER-FSE Rhône-Alpes 2014-2020": "Auvergne-Rhône-Alpes",
    "Programme opérationnel des Pays de la Loire": "Pays de la Loire",
    "Programme opérationnel FEDER-FSE Franche-Comté et massif du Jura 2014-2020": "Bourgogne-Franche-Comté",
    "Programme opérationnel FEDER-FSE Guyane 2014-2020": "Guyane",
    "Programme Opérationnel FEDER Alsace 2014-2020": "Grand Est",
    "Programme Opérationnel FEDER-FSE Provence Alpes Côte d'Azur 2014-2020": "Provence-Alpes-Côte d'Azur",
    "Programme Opérationnel FSE Alsace 2014-2020": "Grand Est",
    "PO FEDER-FSE Corse 2014-2020": "Corse",
    "Programme Opérationnel FEDER Mayotte 2014-2020": "Mayotte",
    "Programme opérationnel FEDER Guadeloupe et Saint-Martin Etat 2014-2020": "Guadeloupe",
    # Nationaux / interrégionaux : pas de région unique (None), pas un trou.
    "Programme opérationnel FEAD 2014-2020": None,
    "PNAT Europ'Act 2014-2020": None,
    "Programme opérationnel interrégionnal Massif Central FEDER 2014-2020": None,
    "Programme opérationnel Interrégional FEDER Loire 2014-2020": None,
    "Programme opérationnel Interrégional FEDER du Massif des Alpes 2014-2020": None,
    "Programme opérationnel Interrégional FEDER Rhône-Saône 2014-2020": None,
    "Programme opérationnel Interrégional FEDER Pyrénées 2014-2020": None,
}

# --- 2021-2027 : les colonnes viennent du garde-fou d'ingestion, pas d'une copie ---
#
# Correspondance clé sémantique de `profiler_source` → clé interne de
# `schema_source.COLONNES_ATTENDUES`. On ne recopie pas les libellés réels ici :
# la source 2021-2027 est republiée 5 fois par an et mélange déjà les deux
# apostrophes (`schema_source`). Passer par `build_cols` fait profiter le profil
# du même contrôle que `ingest.py` — un réordonnancement de la source fait
# échouer la génération avec un message qui nomme la position fautive, au lieu de
# produire un profil faux en silence (issues #45, #69).
_CLES_SEMANTIQUES_2021_2027 = {
    "numero_operation": "numero_op",
    "programme": "libelle_prog",
    "beneficiaire": "nom_benef",
    "fonds": "fonds",
    "region": "region",
    "departement": "departement",
    # 2021-2027 porte des objectifs stratégiques/spécifiques ; 2014-2020 un
    # « Domaine d'intervention ». La clé sémantique est commune, le libellé
    # affiché par la page vient du profil — les deux périodes ne sont pas
    # comparables pour autant (cf. #68).
    "dimension_thematique": "objectif_strat",
    # Il n'y a pas de date de *programmation* dans cette source : la date qui
    # marque l'entrée d'une opération est celle de sa première convention. Le
    # profil expose le libellé réel pour que la page nomme ce qu'elle montre.
    "date_programmation": "date_convention",
    "montant_ue": "montant_ue",
    "depenses": "depenses",
    "pays": "pays",
}


def cols_2021_2027(df):
    """Mapping des colonnes 2021-2027, vérifié par `schema_source.build_cols`."""
    cols_internes = build_cols(df.columns)
    return {
        semantique: cols_internes[interne]
        for semantique, interne in _CLES_SEMANTIQUES_2021_2027.items()
    }


# Un descripteur par **source** (un fichier) : libellé lisible, période,
# où trouver le fichier, quelle feuille lire, et comment ses colonnes réelles se
# mappent aux clés sémantiques de `profiler_source`. Le mapping de colonnes par
# source est aussi le germe du schéma multi-période de #12 — à consolider quand
# l'ingestion 2014-2020 sera câblée.
#
# Champs : `feuille` accepte un nom ou un index (2021-2027 date le nom de sa
# feuille à chaque export : « LISTE OPERATION AU 16 03 2026 » — seul l'index est
# stable) ; `cols` accepte un dict figé ou un callable `df -> dict` ; `date_source`
# est facultative et retombe sinon sur le préfixe daté du nom de fichier.
SOURCES = {
    "2014-2020-synergie": {
        "label": "Synergie national (FEDER/FSE/IEJ/FEAD)",
        "periode": "2014-2020",
        "motif_fichier": "liste_operations_synergie_*.xlsx",
        "feuille": "Liste opérations synergie 14 20",
        "date_source": "2023-08-30",  # feuille « Informations » du fichier
        "programme_to_region": PROGRAMME_TO_REGION_2014_2020,
        "cols": {
            "numero_operation": "Numéro Opération",
            "programme": "Libellé programme",
            "beneficiaire": "Nom du bénéficiaire",
            "fonds": "Fonds",
            "region": "Région de l'opération",
            "departement": "Département de l’opération",
            "dimension_thematique": "Domaine d’intervention",
            "date_programmation": "Date de programmation",
            "montant_ue": "Montant UE programmé",
            "depenses": "Total des dépenses éligibles programmées",
            "pays": "Pays",
        },
    },
    "2021-2027-conventionnees": {
        "label": "Opérations conventionnées (FEDER/FSE+/FTJ)",
        "periode": "2021-2027",
        "motif_fichier": "*_liste_operations_conventionnees_*.xlsx",
        "feuille": 0,
        # `date_source` omise : le nom du fichier porte le millésime de l'export
        # (« 20260316_… »), déjà lu par `schema_source.millesime_du_fichier`.
        # C'est la source que `ingest.py` transforme en `data.json` : son profil
        # décrit donc la donnée qui alimente réellement le reste du dashboard.
        "programme_to_region": PROGRAMME_TO_REGION,
        "cols": cols_2021_2027,
    },
}


def trouver_fichier(motif):
    fichiers = sorted(RAW_DIR.glob(motif))
    if not fichiers:
        raise SystemExit(
            f"Aucun fichier {motif} dans {RAW_DIR}. Déposer le XLSX source de la "
            "période avant de générer son profil."
        )
    return fichiers[-1]


def main(source_id):
    if source_id not in SOURCES:
        raise SystemExit(f"Source inconnue : {source_id!r}. Connues : {list(SOURCES)}")
    conf = SOURCES[source_id]

    chemin = trouver_fichier(conf["motif_fichier"])
    print(f"📖 Lecture : {chemin.name} (feuille « {conf['feuille']} »)")
    df = pd.read_excel(chemin, sheet_name=conf["feuille"])
    print(f"✅ {len(df)} opérations, {df.shape[1]} colonnes")

    # `cols` figé (2014-2020) ou calculé depuis les colonnes réelles (2021-2027,
    # via le contrôle de schéma) — voir le commentaire de SOURCES.
    cols = conf["cols"](df) if callable(conf["cols"]) else conf["cols"]

    # Rattachement par programme sur libellé **normalisé**, comme `ingest.py` : un
    # `.get` direct comparerait les libellés au caractère près et le profil
    # signalerait comme non rattachables des opérations que le pipeline rattache
    # (issue #71). La page « Validation de la source » a trouvé ce défaut : elle
    # doit en refléter la correction, pas la reproduire.
    programme_to_region = conf.get("programme_to_region")
    deriver_region = None
    if programme_to_region:
        index = indexer_programmes(programme_to_region)
        def deriver_region(libelle):
            return region_du_programme(libelle, index)

    profil = {
        "source_id": source_id,
        "source_label": conf["label"],
        "periode": conf["periode"],
        "fichier_source": chemin.name,
        # À défaut d'une date déclarée (feuille « Informations » du fichier
        # Synergie), le préfixe daté du nom de fichier fait foi.
        "date_source": conf.get("date_source") or millesime_du_fichier(chemin),
        "date_generation": date.today().isoformat(),
        "profil": profiler_source(df, cols, deriver_region=deriver_region),
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    sortie = OUTPUT_DIR / f"profil_{source_id}.json"
    sortie.write_text(json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Profil écrit : {sortie.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2014-2020-synergie")
