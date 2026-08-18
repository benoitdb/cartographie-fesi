"""
Rapprochement approché (fuzzy) de noms de bénéficiaires, pour repérer les cas où un même
bénéficiaire est saisi sous une forme légèrement différente d'une région à l'autre dans
SYNERGIE (variantes de casse, d'accents, de forme juridique) — ce que l'égalité stricte de
detect_regroupements_beneficiaire (dashboard/utils/stats.py) ne peut pas capter.

Restreint volontairement aux paires dont les opérations touchent des régions disjointes :
le cas intra-région est déjà couvert par le rapprochement exact existant, pas besoin de le
refaire ici. Voir issue #23.
"""

import re
import unicodedata

from rapidfuzz import fuzz, process
import numpy as np

SCORE_CUTOFF = 90

# Formes juridiques et mentions génériques qui bruitent le score sans être discriminantes
# entre deux bénéficiaires réellement différents.
FORMES_JURIDIQUES = [
    "SARL", "SAS", "SASU", "SA", "EURL", "SCI", "SCOP", "SCP", "GIE", "EARL",
    "ASSOCIATION", "ASSOC", "FONDATION", "ETABLISSEMENT", "ETS",
]
_FORMES_RE = re.compile(r"\b(" + "|".join(FORMES_JURIDIQUES) + r")\b")
_PONCTUATION_RE = re.compile(r"[^\w\s]")
_ESPACES_RE = re.compile(r"\s+")

# Mots-outils ignorés dans la vérification mot-à-mot (ni discriminants ni informatifs).
_MOTS_OUTILS = {"DE", "DU", "DES", "LA", "LE", "LES", "D", "ET", "L", "UN", "UNE"}

# Score minimal, au niveau d'un seul mot, pour considérer deux mots comme la même variante
# (accent/typo) plutôt que deux mots réellement différents — ex. "THONES"/"THÔNES" (typo) vs
# "DROME"/"DORDOGNE" ou "TOULOUSE"/"TOULON" (deux lieux distincts), voir issue #23.
SEUIL_MOT = 85


def _mots_significatifs(nom_normalise):
    return {m for m in nom_normalise.split() if m not in _MOTS_OUTILS and len(m) > 1}


def _residu_explicable(residu, autres_mots):
    """Un résidu de mots (présents d'un côté, absents de l'autre) n'est acceptable que si
    chacun de ses mots a un quasi-équivalent dans l'autre nom — sinon c'est un mot réellement
    différent (souvent un lieu), pas une variante de saisie."""
    return all(any(fuzz.ratio(mot, autre) >= SEUIL_MOT for autre in autres_mots) for mot in residu)


def normalize_nom(nom):
    """Majuscules, accents supprimés, formes juridiques et ponctuation retirées, espaces
    normalisés — réduit une bonne partie des faux négatifs avant même le score fuzzy."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    majuscule = sans_accents.upper()
    sans_ponctuation = _PONCTUATION_RE.sub(" ", majuscule)
    sans_forme = _FORMES_RE.sub(" ", sans_ponctuation)
    return _ESPACES_RE.sub(" ", sans_forme).strip()


class UnionFind:
    """Union-find minimal — regroupe les noms reliés par au moins une paire au-dessus du
    seuil en clusters transitifs (A~B et B~C donnent un seul cluster {A, B, C})."""

    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i, j):
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[ri] = rj


def build_fuzzy_clusters(nom_to_regions, score_cutoff=SCORE_CUTOFF):
    """nom_to_regions : dict nom de bénéficiaire (tel qu'en base) -> set de régions modernes
    où ce nom apparaît. Retourne un dict nom -> cluster_id, uniquement pour les noms dont le
    cluster contient au moins un autre nom (les singletons ne sont pas inclus).

    Calcule la matrice de similarité complète (token_sort_ratio, insensible à l'ordre des
    mots) sur les formes normalisées via rapidfuzz.process.cdist — dtype uint8 pour rester
    léger en mémoire (~n² octets), largement suffisant pour les quelques milliers de noms
    uniques de ce jeu de données. Une paire n'est retenue que si ses régions sont disjointes."""
    noms = list(nom_to_regions.keys())
    normalises = [normalize_nom(n) for n in noms]

    matrix = process.cdist(normalises, normalises, scorer=fuzz.token_sort_ratio, dtype=np.uint8)
    mots = [_mots_significatifs(n) for n in normalises]

    uf = UnionFind(len(noms))
    n = len(noms)
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i, j] < score_cutoff:
                continue
            if nom_to_regions[noms[i]] & nom_to_regions[noms[j]]:
                continue  # régions communes déjà couvertes par le rapprochement exact
            residu_i, residu_j = mots[i] - mots[j], mots[j] - mots[i]
            if not (_residu_explicable(residu_i, mots[j]) and _residu_explicable(residu_j, mots[i])):
                continue  # le score global est trompé par un mot différent (souvent un lieu)
            uf.union(i, j)

    cluster_members = {}
    for idx in range(n):
        root = uf.find(idx)
        cluster_members.setdefault(root, []).append(idx)

    resultat = {}
    for root, membres in cluster_members.items():
        if len(membres) < 2:
            continue
        cluster_id = f"fuzzy_{root}"
        for idx in membres:
            resultat[noms[idx]] = cluster_id
    return resultat
