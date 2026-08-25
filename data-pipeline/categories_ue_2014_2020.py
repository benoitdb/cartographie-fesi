"""
Catégorie de région 2014-2020 par région moderne, écrite dans
data/processed/categories_ue_2014_2020.json pour le dashboard (issue #81).

Pourquoi un fichier séparé plutôt qu'un champ de plus dans region_metadata.json :
ce dernier est produit par region_metadata.py, qui **appelle Wikidata**. Y ajouter
la catégorie 2014-2020 obligerait à refaire un appel réseau pour publier une donnée
qui n'en dépend pas, et ferait dépendre une transcription réglementaire de la
disponibilité d'un service tiers. Ici, comme programme_totals.py, aucun appel
réseau : tout est dérivé de reference/cohesion_ue_2014_2020.py, déjà committé.

Deux champs par région, et la distinction est le sujet même de l'issue :

- `categorie_ue` : la catégorie de la période, ou None quand la région est
  **mixte** — six régions modernes sur treize réunissent des anciennes régions de
  catégories différentes (contre une seule en 2021-2027). None, et non un libellé
  « mixte » à parser côté dashboard : la catégorie n'existe pas à cette maille,
  c'est un fait sur la donnée et pas une chaîne à interpréter.
- `composantes` : les anciennes régions et leur catégorie, toujours renseignées,
  y compris pour une région homogène. C'est ce qui permet au dashboard d'afficher
  un intervalle de plafonds là où un plafond unique n'existe pas, et de dire de
  quelles anciennes régions il vient.

Ce fichier ne contient **aucun montant** : pondérer les régions mixtes par leur
dotation réelle demanderait la table des dotations de l'Accord de partenariat
2014-2020, non transcrite à ce jour (issue #93). Le repli qualitatif retenu ici
est celui que 2021-2027 utilise déjà quand la donnée budgétaire manque.

Saint-Martin et Normandie peuvent être absentes du fichier de données de la
période sans que ce soit une anomalie (l'une n'a pas de code NUTS2010 propre,
l'autre est hors Synergie — #68) ; ce script exporte ce que la décision 2014/99
permet de rattacher, le dashboard traite l'absence comme « non classifiée ».
"""

import json
from pathlib import Path

from region_mapping import OLD_NAME_TO_MODERN

from reference.cohesion_ue_2014_2020 import NUTS2010_CATEGORIE
from reference.nuts_2014_2020 import NUTS2010_CODE_TO_OLD_REGION

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "categories_ue_2014_2020.json"


def construire():
    composantes = {}
    for nuts_code, old_region in NUTS2010_CODE_TO_OLD_REGION.items():
        moderne = OLD_NAME_TO_MODERN[old_region]
        composantes.setdefault(moderne, []).append([old_region, NUTS2010_CATEGORIE[nuts_code]])

    sortie = {}
    for moderne, entrees in composantes.items():
        entrees.sort()
        categories = {categorie for _, categorie in entrees}
        sortie[moderne] = {
            "categorie_ue": categories.pop() if len(categories) == 1 else None,
            "composantes": entrees,
        }
    return dict(sorted(sortie.items()))


def main():
    sortie = construire()

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    print(f"✅ Écrit dans {OUTPUT_PATH}")
    for region, infos in sortie.items():
        if infos["categorie_ue"]:
            print(f"  {region}: {infos['categorie_ue']}")
        else:
            detail = ", ".join(f"{ancienne} : {categorie}" for ancienne, categorie in infos["composantes"])
            print(f"  {region}: mixte ({detail})")


if __name__ == "__main__":
    main()
