"""
Transferts de solidarité entre catégories de régions (politique de cohésion UE), 2021-2027 —
voir issues #20/#22/#30.

Source primaire : Accord de partenariat des autorités françaises 2021-2027, version 1.4
adoptée par la Commission européenne le 2 juin 2022, Tableau 3A "Transfert entre catégories de
régions (ventilation par année)" et Tableau 3B "Transfert entre catégories de régions (résumé)"
(p.44). PDF fourni manuellement par l'utilisateur (voir feedback-ask-for-manual-fetch).
Transcrit le 2026-08-18.

Mécanisme national et global (pas par-opération, pas par région nommée) : une partie de la
dotation initiale des catégories "Plus développées" et "En transition" est reversée à la
catégorie "Moins développées", au nom du principe de solidarité entre régions (cf. Tableau 3B :
respect des grands équilibres budgétaires, PIB/habitant, stabilité entre les deux périodes de
programmation). Non croisable avec data/processed/data.json (aucune opération ni région n'y est
directement rattachée) — encart purement contextuel, pas un KPI calculé.

Écart d'1€ entre la somme de la ventilation annuelle "Plus développées" ci-dessous
(447 742 363) et le total publié au Tableau 3B (447 742 362) : artefact d'arrondi dans le
document source, pas une erreur de transcription (la ventilation "En transition" retombe
exactement sur son total publié).
"""

from collections import namedtuple

TransfertAnnuel = namedtuple("TransfertAnnuel", "categorie_origine montants_par_annee total_publie")

# montants_par_annee : {année: montant en €}, 2021 absent du Tableau 3A (aucun transfert cette
# année-là — la programmation 2021 a été reventilée sur 2022-2025, voir note du Tableau 3B).
TRANSFERTS_VERS_MOINS_DEVELOPPEES = [
    TransfertAnnuel(
        "Plus développées",
        {2022: 76_477_858, 2023: 77_709_572, 2024: 78_966_072, 2025: 80_248_373, 2026: 66_502_492, 2027: 67_837_996},
        447_742_362,
    ),
    TransfertAnnuel(
        "En transition",
        {2022: 111_621_188, 2023: 113_417_164, 2024: 115_245_402, 2025: 117_117_323, 2026: 97_057_044, 2027: 99_019_092},
        653_477_213,
    ),
]

# Part de la dotation initiale de chaque catégorie transférée (Tableau 3B, colonne "Part de la
# dotation initiale transférée") — donnée telle quelle, pas recalculée à partir d'une dotation
# initiale non reprise ici.
PART_DOTATION_TRANSFEREE = {
    "Plus développées": 0.20,
    "En transition": 0.06,
}

_TOLERANCE = 5


def _verify_totals():
    for transfert in TRANSFERTS_VERS_MOINS_DEVELOPPEES:
        somme_annuelle = sum(transfert.montants_par_annee.values())
        ecart = abs(somme_annuelle - transfert.total_publie)
        assert ecart <= _TOLERANCE, (
            f"{transfert.categorie_origine} : somme annuelle {somme_annuelle} vs total publié "
            f"{transfert.total_publie} (écart {ecart} > tolérance {_TOLERANCE})"
        )


_verify_totals()
