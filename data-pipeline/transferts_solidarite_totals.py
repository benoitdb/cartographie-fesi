"""
Écrit data/processed/transferts_solidarite.json à partir de reference/transferts_solidarite.py
(Tableau 3A/3B) — voir issue #30. Purement informationnel, pas d'agrégation avec data.json.
"""

import json
from pathlib import Path

from reference.transferts_solidarite import PART_DOTATION_TRANSFEREE, TRANSFERTS_VERS_MOINS_DEVELOPPEES

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "transferts_solidarite.json"


def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    payload = {
        "transferts": [
            {
                "categorie_origine": t.categorie_origine,
                "montants_par_annee": {str(annee): montant for annee, montant in t.montants_par_annee.items()},
                "total_publie": t.total_publie,
                "part_dotation_transferee": PART_DOTATION_TRANSFEREE[t.categorie_origine],
            }
            for t in TRANSFERTS_VERS_MOINS_DEVELOPPEES
        ]
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ Transferts de solidarité écrits dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
