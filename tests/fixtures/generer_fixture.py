"""Régénère la fixture de test du dashboard à partir des données réelles du poste.

À relancer quand le schéma de `data.json` change (nouvelle colonne, colonne
renommée) — sinon les tests de fumée valideraient un schéma périmé.

    cd "Cartographie FESI" && venv/bin/python tests/fixtures/generer_fixture.py

Ce que la fixture contient, et pourquoi (voir aussi README.md à côté) :

- un échantillon **stratifié par région** des opérations, pour que les 19 régions
  et les 3 fonds soient représentés — un tirage aléatoire simple laisserait des
  pages sans données et le test de fumée ne prouverait plus rien pour elles ;
- le champ `Objectifs et réalisations escomptés et effectifs` **tronqué** : il
  pèse 61,5 % du fichier réel et n'est lu nulle part dans `dashboard/`. Il est
  conservé (tronqué) plutôt que supprimé, pour que le schéma reste fidèle ;
- le bloc `aggregates` **tel quel**, donc décrivant le jeu COMPLET et non
  l'échantillon. C'est assumé pour un test de fumée, et c'est la raison pour
  laquelle cette fixture ne doit pas servir à des assertions sur des valeurs.
"""

import json
import shutil
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
SOURCE = RACINE / "data" / "processed"
CIBLE = Path(__file__).resolve().parent / "dashboard"

# Assez pour que chaque région ait de quoi remplir ses graphiques, assez peu pour
# que la fixture reste sous le mégaoctet.
OPS_PAR_REGION = 20
CHAMP_VOLUMINEUX = "Objectifs et réalisations escomptés et effectifs"
LONGUEUR_MAX = 200

# Petits fichiers lus par le dashboard mais gitignorés : copiés intégralement.
COPIES_INTEGRALES = ["beneficiaires_fuzzy.json", "transferts_solidarite.json"]


def region_de(op):
    regions = op.get("regions_modernes") or []
    return regions[0] if regions else "(sans région)"


def main():
    CIBLE.mkdir(parents=True, exist_ok=True)
    data = json.loads((SOURCE / "data.json").read_text(encoding="utf-8"))

    par_region = defaultdict(list)
    for op in data["operations"]:
        par_region[region_de(op)].append(op)

    echantillon = []
    for region in sorted(par_region):
        for op in par_region[region][:OPS_PAR_REGION]:
            op = dict(op)
            texte = op.get(CHAMP_VOLUMINEUX)
            if isinstance(texte, str) and len(texte) > LONGUEUR_MAX:
                op[CHAMP_VOLUMINEUX] = texte[:LONGUEUR_MAX] + "…"
            echantillon.append(op)

    data["operations"] = echantillon
    data["metadata"]["fixture"] = (
        f"Échantillon de test : {len(echantillon)} opérations sur "
        f"{data['metadata']['total_operations']}, stratifiées par région. "
        f"Le bloc 'aggregates' décrit le jeu COMPLET, pas cet échantillon."
    )

    cible_data = CIBLE / "data.json"
    cible_data.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for nom in COPIES_INTEGRALES:
        shutil.copy(SOURCE / nom, CIBLE / nom)

    print(f"{len(echantillon)} opérations sur {len(par_region)} régions")
    for chemin in sorted(CIBLE.glob("*.json")):
        print(f"  {chemin.stat().st_size // 1024:>5} Ko  {chemin.name}")


if __name__ == "__main__":
    main()
