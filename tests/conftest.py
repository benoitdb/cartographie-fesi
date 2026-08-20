import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `data-pipeline/` n'est pas un paquet installable (nom avec tiret, scripts
# exécutés depuis leur propre dossier) : on l'ajoute au sys.path comme le font
# les scripts eux-mêmes quand ils s'importent entre eux.
sys.path.insert(0, str(ROOT / "data-pipeline"))
