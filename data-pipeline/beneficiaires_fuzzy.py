"""
Précalcule les rapprochements approchés (fuzzy) de noms de bénéficiaires entre régions
disjointes (voir beneficiaire_matching.py et issue #23), à partir des opérations déjà
harmonisées dans data.json.

Écrit data/processed/beneficiaires_fuzzy.json : {nom_de_beneficiaire: cluster_id}, restreint
aux noms dont le cluster contient au moins un autre nom. Lu par le dashboard
(utils.stats.detect_regroupements_beneficiaire) pour compléter le rapprochement exact
existant avec les cas où la saisie diffère d'une région à l'autre.
"""

import json
from collections import defaultdict
from pathlib import Path

from beneficiaire_matching import build_fuzzy_clusters

DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "data.json"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "beneficiaires_fuzzy.json"


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    nom_to_regions = defaultdict(set)
    for op in data["operations"]:
        nom = op.get("Nom du bénéficiaire")
        if not nom:
            continue
        nom_to_regions[nom].update(op.get("regions_modernes") or [])

    clusters = build_fuzzy_clusters(dict(nom_to_regions))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)

    nb_clusters = len(set(clusters.values()))
    print(f"✅ {len(clusters)} noms rapprochés en {nb_clusters} cluster(s) inter-région, écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
