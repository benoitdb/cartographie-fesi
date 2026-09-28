"""
Précalcule les rapprochements approchés (fuzzy) de noms de bénéficiaires entre régions
disjointes (voir beneficiaire_matching.py et issue #23), à partir des opérations déjà
harmonisées dans data.parquet — et non data.json, qui ne porte plus les opérations
depuis la PR #132 (lire l'ancien emplacement levait KeyError : issue #184).

Écrit data/processed/beneficiaires_fuzzy.json : {nom_de_beneficiaire: cluster_id}, restreint
aux noms dont le cluster contient au moins un autre nom. Lu par le dashboard
(utils.stats.detect_regroupements_beneficiaire) pour compléter le rapprochement exact
existant avec les cas où la saisie diffère d'une région à l'autre.
"""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
from beneficiaire_matching import build_fuzzy_clusters

DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "data.parquet"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "beneficiaires_fuzzy.json"


def main():
    operations = pd.read_parquet(DATA_PATH, columns=["Nom du bénéficiaire", "regions_modernes"])

    nom_to_regions = defaultdict(set)
    for nom, regions in operations.itertuples(index=False):
        # Un nom manquant revient du Parquet en NaN, que `not nom` laisse passer
        # (NaN est vrai) jusqu'à un TypeError dans normalize_nom.
        if pd.isna(nom) or not nom:
            continue
        # `regions_modernes` revient du Parquet en numpy.ndarray : `regions or []`
        # lèverait « truth value is ambiguous » sur un tableau non vide.
        if regions is not None:
            nom_to_regions[nom].update(regions)

    clusters = build_fuzzy_clusters(dict(nom_to_regions))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)

    nb_clusters = len(set(clusters.values()))
    print(f"✅ {len(clusters)} noms rapprochés en {nb_clusters} cluster(s) inter-région, écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
