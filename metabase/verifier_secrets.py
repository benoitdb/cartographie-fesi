"""Contrôle local des prérequis de sécurité, sans afficher de secret."""

import stat
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
ENV = RACINE / ".env"
REQUIS = {
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "METABASE_APP_USER",
    "METABASE_APP_PASSWORD", "FESI_LOADER_USER", "FESI_LOADER_PASSWORD",
    "FESI_READER_USER", "FESI_READER_PASSWORD", "MB_ADMIN_EMAIL", "MB_ADMIN_PASSWORD",
}


def main():
    if not ENV.exists():
        sys.exit(".env absent : copier .env.example puis renseigner les valeurs locales.")
    mode = stat.S_IMODE(ENV.stat().st_mode)
    if mode != 0o600:
        sys.exit(f".env doit être en mode 600 (mode actuel : {mode:o}).")
    cles = {ligne.split("=", 1)[0].strip() for ligne in ENV.read_text().splitlines() if "=" in ligne}
    manquantes = sorted(REQUIS - cles)
    if manquantes:
        sys.exit("Variables manquantes : " + ", ".join(manquantes))
    print("OK : permissions et variables requises présentes.")


if __name__ == "__main__":
    main()
