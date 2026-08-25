"""Génère le profil JSON d'une source d'opérations, une par fichier.

Lit un XLSX brut de `data/raw/`, appelle `profiler_source`, et écrit
`data/processed/profil_<source>.json`. Idempotent, rejouable à chaque nouveau
millésime. Le JSON est committé (comme `programme_totals.json`) pour que la page
« Validation de la source » du dashboard tourne sans le XLSX brut.

Tout ce qui décrit un fichier — motif, feuille, schéma, date, table
programme → région — vit dans `sources.py`, partagé avec `ingest.py`. Ajouter une
source, c'est ajouter une entrée à `sources.SOURCES` et relancer : le dashboard
la découvre par glob.

Usage :
    python profil_source.py                       # défaut : 2014-2020-synergie
    python profil_source.py 2014-2020-synergie
    python profil_source.py 2021-2027-conventionnees
"""

import json
import sys
from datetime import date
from pathlib import Path

from profilage_source import profiler_source
from region_mapping import indexer_programmes, region_du_programme
from schema_source import SchemaSourceError
from sources import cols_profil, lire_dataframe, millesime, source, trouver_fichier

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"


def main(source_id):
    conf = source(source_id)

    chemin = trouver_fichier(conf)
    if "feuilles" in conf:
        noms_feuilles = ", ".join(f["nom"] for f in conf["feuilles"])
        print(f"📖 Lecture : {chemin.name} (feuilles « {noms_feuilles} »)")
    else:
        print(f"📖 Lecture : {chemin.name} (feuille « {conf['feuille']} »)")
    df = lire_dataframe(conf, chemin)
    print(f"✅ {len(df)} opérations, {df.shape[1]} colonnes")

    # Libellés réels tirés du contrôle de schéma, jamais recopiés : un
    # réordonnancement de la source fait échouer la génération en nommant la
    # position fautive, au lieu de produire un profil faux en silence.
    cols = cols_profil(conf, df.columns)

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
        "date_source": millesime(conf, chemin),
        "date_generation": date.today().isoformat(),
        "profil": profiler_source(df, cols, deriver_region=deriver_region),
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    sortie = OUTPUT_DIR / f"profil_{source_id}.json"
    sortie.write_text(json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Profil écrit : {sortie.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else "2014-2020-synergie")
    except SchemaSourceError as erreur:
        raise SystemExit(str(erreur)) from erreur
