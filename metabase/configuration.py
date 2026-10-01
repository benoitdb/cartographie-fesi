"""Configuration locale Metabase, sans valeur de repli pour les comptes."""

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def charger_env(environnement=None, chemin=None):
    environnement = os.environ if environnement is None else environnement
    chemin = RACINE / ".env" if chemin is None else Path(chemin)
    if chemin.exists():
        for ligne in chemin.read_text().splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                environnement.setdefault(cle.strip(), valeur.strip())
    return environnement


def exiger(environnement, *cles):
    manquantes = [cle for cle in cles if not environnement.get(cle)]
    if manquantes:
        raise RuntimeError(f"Variables de configuration manquantes : {', '.join(manquantes)}")
    return [environnement[cle] for cle in cles]


def connexion_fesi(role, environnement=None):
    environnement = charger_env(environnement)
    utilisateur, mot_de_passe, base = exiger(
        environnement, f"FESI_{role.upper()}_USER", f"FESI_{role.upper()}_PASSWORD", "POSTGRES_DB"
    )
    return {
        "host": environnement.get("POSTGRES_HOST", "localhost"),
        "port": int(environnement.get("POSTGRES_PORT", "5437")),
        "dbname": base,
        "user": utilisateur,
        "password": mot_de_passe,
    }
