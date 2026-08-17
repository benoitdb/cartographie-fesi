"""
Écrit data/processed/interreg.json à partir de reference/interreg.py (Tableau 10) — voir
issue #19. Purement une liste (cci/intitulé/type), aucun montant à agréger contrairement aux
autres scripts *_totals.py de ce dossier.
"""

import json
from pathlib import Path

from reference.interreg import PROGRAMMES_INTERREG

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "interreg.json"


def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    programmes = [p._asdict() for p in PROGRAMMES_INTERREG]
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(programmes, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(programmes)} programmes écrits dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
