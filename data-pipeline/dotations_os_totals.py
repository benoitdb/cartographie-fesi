"""
Écrit data/processed/dotations_os.json à partir de reference/dotations_os.py (Tableau 8,
national uniquement) — voir issue #21. Même rôle que programme_totals.py pour le Tableau 9B,
en plus simple : pas de dimension région ici (le Tableau 8 ne ventile pas par région nommée,
voir docstring de reference/dotations_os.py et issue #28).
"""

import json
from pathlib import Path

from reference.dotations_os import DOTATIONS_OS_PAR_FONDS

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "dotations_os.json"


def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(DOTATIONS_OS_PAR_FONDS, f, ensure_ascii=False, indent=2)
    print(f"✅ Écrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
