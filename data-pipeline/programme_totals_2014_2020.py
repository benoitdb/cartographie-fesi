"""
Enveloppes programmées 2014-2020 par région et par fonds, dans les libellés de fonds des
données engagées — pendant de `programme_totals.py` pour la période précédente.

Écrit deux fichiers :

- `data/processed/programme_totals_2014_2020.json` : {région: {fonds: montant UE}}, même
  forme que `programme_totals.json`, directement consommable par le pilotage ;
- `data/processed/programme_detail_2014_2020.json` : ce que le premier agrège et qu'on
  veut pouvoir montrer à part (part REACT-EU, contrepartie FSE de l'IEJ) — fichier séparé
  pour ne rien changer à la forme du premier, même choix qu'en 2021-2027.

Aucun appel réseau, aucune lecture du XLSX : dérivé uniquement de `reference/`, déjà
committé. Peut être relancé à volonté.

Trois règles portent tout le fichier, et aucune n'est devinable depuis les données :

1. **L'IEJ compte double.** La ligne `IEJ` de l'Accord n'est que l'allocation spécifique ;
   la contrepartie FSE, de montant quasi égal, est comptée sur la ligne `FSE` du même
   programme (Accord §1.4.2 et table 1.10, "soutien correspondant du FSE à l'IEJ" :
   473 185 393 € inclus dans le total FSE de 6 026 907 278 €). Une opération IEJ engage
   les deux moitiés. D'où : l'enveloppe IEJ est doublée, **et** la contrepartie est
   retirée de l'enveloppe FSE du même programme — sans quoi elle serait comptée deux fois.
2. **REACT-EU FEDER est un fonds à part, REACT-EU FSE non.** Les données portent un
   libellé `FEDER REACT-EU` distinct, mais rien qui isole le REACT-EU FSE (issue #82) :
   sa maquette est donc fondue dans l'enveloppe `FSE`, quand celle du FEDER reste séparée.
   Voir `react_eu_2014_2020.MAPPING_FONDS_DONNEES`.
3. **Deux fonds engagés n'ont volontairement pas d'enveloppe** et sont donc absents de la
   sortie : le **FEAD**, hors enveloppe structurelle (art. 94), et le **FEDER-FSE** des
   données, qui n'est pas un fonds mais le PNAT Europ'Act — assistance technique
   interfonds, dont l'Accord donne les deux lignes FEDER et FSE séparément. Les agréger
   sous un fonds `FEDER-FSE` inventerait une enveloppe que le document ne pose pas ;
   l'écran doit dire que ces deux fonds sont hors rapprochement, pas afficher un zéro.
"""

import json
from collections import defaultdict
from pathlib import Path

from reference.programmes_2014_2020 import (
    ALLOCATION_SPECIFIQUE_IEJ,
    CONTREPARTIE_FSE_IEJ,
    DOTATIONS,
    programme,
)
from reference.react_eu_2014_2020 import MAPPING_FONDS_DONNEES, MAQUETTES

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "programme_totals_2014_2020.json"
DETAIL_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "programme_detail_2014_2020.json"

# Clé de regroupement des programmes nationaux et interrégionaux, alignée sur le
# périmètre "Volet national" du dashboard (opérations is_national=True).
CLE_NATIONAL = "national"


def cle_region(cci):
    return programme(cci).region or CLE_NATIONAL


def contrepartie_fse(montant_iej_specifique):
    """Part de la contrepartie FSE nationale revenant à une allocation spécifique IEJ.

    La contrepartie n'est publiée qu'en total national : elle est répartie au prorata de
    l'allocation spécifique, ce qu'autorise le règlement 1304/2013 (art. 22 : contrepartie
    appariée à l'allocation spécifique) et que corrobore l'égalité des deux totaux
    nationaux à 0,4 % près.
    """
    return round(CONTREPARTIE_FSE_IEJ * montant_iej_specifique / ALLOCATION_SPECIFIQUE_IEJ)


def calculer():
    """(totaux, detail) — région -> fonds -> montant UE programmé."""
    totaux = defaultdict(lambda: defaultdict(int))
    react_eu = defaultdict(lambda: defaultdict(int))
    contreparties = defaultdict(int)

    for d in DOTATIONS:
        region = cle_region(d.cci)
        if d.fonds == "IEJ":
            part = contrepartie_fse(d.montant_ue)
            totaux[region]["IEJ"] += d.montant_ue + part
            # Retirée du FSE du même programme : elle y figure dans l'Accord, et
            # l'opération IEJ qui la consomme est déjà comptée côté IEJ.
            totaux[region]["FSE"] -= part
            contreparties[region] += part
        else:
            totaux[region][d.fonds] += d.montant_ue

    for m in MAQUETTES:
        region = cle_region(m.cci)
        fonds = MAPPING_FONDS_DONNEES[m.fonds]
        totaux[region][fonds] += m.montant_ue
        react_eu[region][fonds] += m.montant_ue

    detail = {
        # Part REACT-EU incluse dans les totaux ci-dessus, isolée pour l'affichage : sa
        # provenance (rapport d'évaluation ANCT 2024) diffère de celle du reste (Accord
        # de partenariat 2019) et doit pouvoir être dite à l'écran.
        "react_eu": {r: dict(v) for r, v in react_eu.items()},
        # Contrepartie FSE de l'IEJ, ajoutée à l'enveloppe IEJ et retranchée de
        # l'enveloppe FSE de la même région.
        "contrepartie_fse_iej": dict(contreparties),
    }
    return {r: dict(v) for r, v in totaux.items()}, detail


def main():
    totaux, detail = calculer()

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(totaux, f, ensure_ascii=False, indent=2)
    print(f"✅ Écrit dans {OUTPUT_PATH}")
    for region, fonds_totaux in sorted(totaux.items()):
        ligne = ", ".join(f"{f}={v / 1e6:,.1f} M€".replace(",", " ") for f, v in sorted(fonds_totaux.items()))
        print(f"  {region}: {ligne}")

    with open(DETAIL_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)
    print(f"✅ Écrit dans {DETAIL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
