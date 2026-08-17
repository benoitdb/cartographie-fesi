"""
Liste des programmes Interreg (coopération territoriale européenne) auxquels la France
participe, 2021-2027 — voir issue #19.

Source primaire : Accord de partenariat des autorités françaises 2021-2027, version 1.4
adoptée par la Commission européenne le 2 juin 2022, Tableau 10 "Liste des programmes
Interreg prévus" (p.49-50). PDF fourni manuellement par l'utilisateur (voir
feedback-ask-for-manual-fetch). Transcrit le 2026-08-17.

Contrairement aux Tableaux 8/9B, ce tableau ne donne AUCUN montant — seulement le code CCI et
l'intitulé de chaque programme. Aucune opération Interreg n'existe par ailleurs dans
data/processed/data.json (vérifié : les 21 valeurs de NUMCCI présentes sont toutes préfixées
"2021FR...", série distincte des codes Interreg "2021TC..." ci-dessous — absence structurelle,
pas un problème d'étiquetage). Cette liste est donc purement informationnelle : pas de
montant, pas d'opération, pas de région française associée (programmes multi-pays, pilotés
par une autorité de gestion transnationale, pas par la France seule).

ATTENTION collision de vocabulaire (vérifié le 2026-08-17, question posée par l'utilisateur) :
le champ is_interregional de data.json (13 opérations) n'a AUCUN rapport avec Interreg — il
signale une opération française "classique" dont le territoire couvre plusieurs régions
françaises au sein d'un même programme régional (ex. une action "massif des Alpes" à cheval
Auvergne-Rhône-Alpes/PACA), probablement liée aux "thématiques interrégionales (massifs,
fleuves)" mentionnées dans l'Accord de partenariat (enveloppe dédiée de 203 750 000 €, hors
p.47). Vérifié : les 13 opérations is_interregional portent toutes un NUMCCI de la série
"2021FR..." (programmes français), aucune ne correspond à un programme Interreg réel.

Type de coopération (classification officielle Interreg) :
- VI-A : transfrontalier (deux pays limitrophes)
- VI-B : transnational (grande zone géographique, plusieurs pays)
- VI-D : régions ultrapériphériques (coopération avec des pays tiers voisins d'un DROM)
"""

from collections import namedtuple

ProgrammeInterreg = namedtuple("ProgrammeInterreg", "cci intitule type")

PROGRAMMES_INTERREG = [
    ProgrammeInterreg("2021TC16RFCB006", "Spain-France-Andorra (POCTEFA)", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB031", "Italy-France (Maritime)", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB032", "France-Italy (ALCOTRA)", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB036", "France-Germany-Switzerland (Upper Rhine)", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB037", "France-Switzerland", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB039", "Belgium-France (Wallonie-Vlaanderen-France)", "VI-A"),
    ProgrammeInterreg("2021TC16RFCB040", "France-Belgium-Germany-Luxembourg (Grande Région/Großregion)", "VI-A"),

    ProgrammeInterreg("2021TC16RFTN001", "Alpine Space", "VI-B"),
    ProgrammeInterreg("2021TC16RFTN002", "Atlantic Area", "VI-B"),
    ProgrammeInterreg("2021TC16RFTN004", "North Sea", "VI-B"),
    ProgrammeInterreg("2021TC16RFTN005", "North West Europe", "VI-B"),
    ProgrammeInterreg("2021TC16RFTN006", "South West Europe (SUDOE)", "VI-B"),
    ProgrammeInterreg("2021TC16FFTN001", "Euro Mediterranean (EURO MED)", "VI-B"),
    ProgrammeInterreg("2021TC16NXTN001", "NEXT Mediterranean Sea Basin (NEXT MED)", "VI-B"),

    ProgrammeInterreg("2021TC16FFOR002", "Canal du Mozambique", "VI-D"),
    ProgrammeInterreg("2021TC16FFOR003", "Caraïbes", "VI-D"),
    ProgrammeInterreg("2021TC16FFOR004", "Océan Indien", "VI-D"),
    ProgrammeInterreg("2021TC16FFOR005", "Amazonie", "VI-D"),
]

_TOTAL_ATTENDU = 18


def _verify_totals():
    assert len(PROGRAMMES_INTERREG) == _TOTAL_ATTENDU, f"{len(PROGRAMMES_INTERREG)} programmes transcrits, {_TOTAL_ATTENDU} attendus"
    ccis = [p.cci for p in PROGRAMMES_INTERREG]
    assert len(ccis) == len(set(ccis)), "code CCI en double"
    assert all(cci.startswith("2021TC") for cci in ccis), "un code CCI ne suit pas la série Interreg 2021TC..."


_verify_totals()
