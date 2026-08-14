"""
Totaux programmés (Tableau 9B, reference/programmes_2021_2027.py) par région et par fonds,
tous catégories de région confondues (y compris l'allocation additionnelle
"Ultrapériphériques" pour les DOM/Saint-Martin — comptée dans le même total que leur
catégorie de base, car les opérations engagées de data.json ne distinguent pas de quelle
enveloppe elles proviennent).

Écrit data/processed/programme_totals.json, lu par le dashboard (utils.data_loader) pour
calculer un taux de consommation par région/fonds — voir issue #6 du backlog. Contrairement
à region_metadata.py, ce script ne fait aucun appel réseau (dérivé uniquement de
programmes_2021_2027.py, déjà committé) : peut être relancé à volonté, aucune raison qu'il
diverge du code source sauf mise à jour de programmes_2021_2027.py lui-même.

Les programmes nationaux (region=None dans PROGRAMMES) sont agrégés sous la clé "national",
qui correspond au périmètre "Volet national" du dashboard (opérations is_national=True) —
à l'exception du programme FEAMPA, hors périmètre FEDER/FSE+/FTJ actuel (voir issue #14).
"""

import json
from collections import defaultdict
from pathlib import Path

from reference.programmes_2021_2027 import PROGRAMMES

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "programme_totals.json"


def main():
    totals = defaultdict(lambda: defaultdict(int))
    for p in PROGRAMMES:
        if p.fonds == "FEAMPA":
            continue
        cle_region = p.region if p.region else "national"
        totals[cle_region][p.fonds] += p.contribution_ue

    output = {region: dict(fonds_totals) for region, fonds_totals in totals.items()}

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Écrit dans {OUTPUT_PATH}")
    for region, fonds_totals in sorted(output.items()):
        detail = ", ".join(f"{f}={v / 1e6:,.1f} M€".replace(",", " ") for f, v in fonds_totals.items())
        print(f"  {region}: {detail}")


if __name__ == "__main__":
    main()
