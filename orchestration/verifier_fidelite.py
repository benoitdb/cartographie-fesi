"""Une régénération passée par Dagster change-t-elle un chiffre ? (spike #183)

`git diff --exit-code` ne peut pas répondre : chaque JSON porte son
`generated_at`, et chaque Parquet la version de pyarrow qui l'a écrit. Ce
script compare donc les CONTENUS de chaque fichier modifié contre `HEAD` :
JSON sans `metadata.generated_at`, Parquet cellule à cellule.

    orchestration/venv/bin/python orchestration/verifier_fidelite.py
"""

import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]


def version_head(chemin: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"HEAD:{chemin}"], cwd=RACINE, capture_output=True, check=True
    ).stdout


def sans_horodatage(octets: bytes) -> dict:
    donnees = json.loads(octets)
    donnees.get("metadata", {}).pop("generated_at", None)
    return donnees


def main() -> int:
    modifies = subprocess.run(
        ["git", "diff", "--name-only", "--", "data/processed", "dbt"],
        cwd=RACINE, capture_output=True, text=True, check=True,
    ).stdout.split()
    ecarts = 0
    for chemin in modifies:
        actuel = (RACINE / chemin).read_bytes()
        avant = version_head(chemin)
        if chemin.endswith(".parquet"):
            identique = pd.read_parquet(io.BytesIO(avant)).equals(
                pd.read_parquet(io.BytesIO(actuel))
            )
        elif chemin.endswith(".json"):
            identique = sans_horodatage(avant) == sans_horodatage(actuel)
        else:
            identique = avant == actuel
        ecarts += not identique
        print(f"{'identique' if identique else 'ÉCART    '}  {chemin}")
    print(f"\n{len(modifies)} fichier(s) réécrit(s), {ecarts} écart(s) de contenu.")
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
