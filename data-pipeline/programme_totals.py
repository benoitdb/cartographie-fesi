"""
Totaux programmés (Tableau 9B, reference/programmes_2021_2027.py) par région et par fonds,
tous catégories de région confondues (y compris l'allocation additionnelle
"Ultrapériphériques" pour les DOM/Saint-Martin — comptée dans le même total que leur
catégorie de base, car les opérations engagées de data.json ne distinguent pas de quelle
enveloppe elles proviennent). Le détail de cette allocation RUP seule est exposé à part dans
programme_detail.json (clé "rup") pour un affichage pédagogique (issue cofinancement/RUP).

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
DETAIL_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "programme_detail.json"


def main():
    totals = defaultdict(lambda: defaultdict(int))
    ftj_article = defaultdict(lambda: defaultdict(int))
    assistance_technique = defaultdict(lambda: defaultdict(int))
    rup = defaultdict(lambda: defaultdict(int))
    for p in PROGRAMMES:
        if p.fonds == "FEAMPA":
            continue
        cle_region = p.region if p.region else "national"
        totals[cle_region][p.fonds] += p.contribution_ue
        assistance_technique[cle_region][p.fonds] += p.assistance_technique
        if p.fonds == "FTJ":
            ftj_article[cle_region][p.categorie] += p.contribution_ue
        if p.categorie == "Ultrapériphériques":
            rup[cle_region][p.fonds] += p.contribution_ue

    output = {region: dict(fonds_totals) for region, fonds_totals in totals.items()}

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Écrit dans {OUTPUT_PATH}")
    for region, fonds_totals in sorted(output.items()):
        detail = ", ".join(f"{f}={v / 1e6:,.1f} M€".replace(",", " ") for f, v in fonds_totals.items())
        print(f"  {region}: {detail}")

    # Détail non couvert par programme_totals.json (voir issue #20/#21) : split FTJ
    # Article 3/4 (classification propre au FTJ, sans lien avec les 3 catégories de cohésion)
    # et enveloppes d'assistance technique par fonds — fichier séparé plutôt qu'ajouté à
    # programme_totals.json pour ne rien changer à sa forme (region -> fonds -> montant),
    # déjà consommée telle quelle par le pilotage programmé/engagé.
    detail_output = {
        "ftj_article": {region: dict(v) for region, v in ftj_article.items()},
        "assistance_technique": {region: dict(v) for region, v in assistance_technique.items()},
        # Allocation additionnelle "Ultrapériphériques" (art. 349 TFUE), en plus de la
        # dotation de catégorie de base (déjà incluse dans totals ci-dessus) — les 6
        # programmes DOM/Saint-Martin uniquement (voir cohesion_ue.py REGION_ULTRAPERIPHERIQUE).
        "rup": {region: dict(v) for region, v in rup.items()},
    }
    with open(DETAIL_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(detail_output, f, ensure_ascii=False, indent=2)
    print(f"✅ Écrit dans {DETAIL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
