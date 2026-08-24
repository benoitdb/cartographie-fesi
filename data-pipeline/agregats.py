"""Calcul des agrégats de `data.json`, isolé du script qui les écrit.

Ces agrégats alimentent tous les totaux affichés par le dashboard : montants par
région, par fonds, par objectif stratégique, et les croisements. Ils étaient
écrits à plat au milieu d'`ingest.py`, dépendant de ses variables globales
(issue #60) — donc ni appelables sur un sous-ensemble, ni testables autrement
qu'en régénérant les 45 Mo du fichier complet, ce qui suppose d'avoir le XLSX
source sous la main.

Deux règles de découpage à connaître avant de lire les fonctions :

- **une opération appartient à une seule des trois partitions** (mono-région,
  interrégionale, volet national) ; les agrégats par région ne portent que sur
  la première, sinon une opération multi-régions serait comptée plusieurs fois
  dans un total censé être une somme ;
- **les agrégats par fonds et par objectif stratégique portent, eux, sur TOUTES
  les opérations** — leur dimension n'a rien de géographique, exclure le volet
  national y créerait un écart inexpliqué avec le montant total.
"""

from collections import namedtuple

Partitions = namedtuple("Partitions", ["mono_region", "interregional", "national"])


def partitionner(df):
    """Répartit les opérations en trois sous-ensembles disjoints, selon les
    drapeaux posés par l'harmonisation des régions (`region_mapping`)."""
    return Partitions(
        mono_region=df[~df["is_interregional"] & ~df["is_national"]],
        interregional=df[df["is_interregional"]],
        national=df[df["is_national"]],
    )


def _resume(subset, cols):
    """Bloc de montants commun à tous les agrégats de premier niveau.

    `float(...)` explicite : sans lui les valeurs restent des `numpy.float64`,
    que `json.dump` refuse de sérialiser."""
    return {
        "count": len(subset),
        "montant_ue_total": float(subset[cols["montant_ue"]].sum()),
        "montant_ue_moyen": float(subset[cols["montant_ue"]].mean()),
        "depenses_total": float(subset[cols["depenses"]].sum()),
        "depenses_moyen": float(subset[cols["depenses"]].mean()),
    }


def _region_principale(df_mono_region):
    """Première région de chaque opération mono-région. Calculée une fois et
    passée aux boucles qui en ont besoin : en faire une lambda réévaluée à
    chaque tour coûtait un parcours complet par région (issue #50)."""
    return df_mono_region["regions_modernes"].apply(lambda x: x[0] if x else None)


def calculer_agregats(df, cols, partitions=None):
    """Agrégats de `data.json`, à partir du DataFrame harmonisé.

    `cols` : mapping {clé interne: libellé réel de la colonne}, tel que le
    construit `schema_source.build_cols`. `partitions` évite de refaire le
    découpage quand l'appelant en a déjà besoin par ailleurs.

    Une partition ou une catégorie vide est **absente** du résultat plutôt que
    présente à zéro : c'est le comportement historique, et le dashboard lit
    certaines de ces clés sans valeur par défaut. Sur un sous-ensemble
    (échantillon de test), s'assurer donc que les trois partitions sont
    représentées.
    """
    partitions = partitions or partitionner(df)
    df_mono_region = partitions.mono_region
    region_principale = _region_principale(df_mono_region)
    regions_mono = sorted(region_principale.dropna().unique())
    fonds_tous = sorted(df[cols["fonds"]].unique())

    # La dimension thématique n'existe pas dans toutes les périodes : 2021-2027 a
    # des objectifs stratégiques, 2014-2020 un « Domaine d'intervention » vide à
    # 100 % dans le fichier Synergie (issues #12, #73). Ses trois blocs sont donc
    # **absents** du résultat quand la clé l'est, plutôt que remplis d'une
    # catégorie « Non spécifié » inventée : une dimension absente de la source ne
    # doit pas ressembler à une dimension mesurée et vide.
    a_objectif = "objectif_strat" in cols
    objectifs_tous = sorted(df[cols["objectif_strat"]].dropna().unique()) if a_objectif else []

    aggregates = {}

    # by_region : mono-région uniquement (cf. docstring du module).
    aggregates["by_region"] = {}
    for region in regions_mono:
        subset = df_mono_region[region_principale == region]
        if len(subset) > 0:
            aggregates["by_region"][region] = _resume(subset, cols)

    if len(partitions.national) > 0:
        aggregates["national"] = _resume(partitions.national, cols)

    if len(partitions.interregional) > 0:
        # Les numéros d'opération en plus du résumé : ces opérations n'apparaissent
        # dans aucune région, la liste permet de les retrouver depuis le dashboard.
        aggregates["interregional"] = {
            **_resume(partitions.interregional, cols),
            "operations": [row[cols["numero_op"]] for _, row in partitions.interregional.iterrows()],
        }

    aggregates["by_fonds"] = {}
    for fonds in fonds_tous:
        aggregates["by_fonds"][fonds] = _resume(df[df[cols["fonds"]] == fonds], cols)

    if a_objectif:
        aggregates["by_objectif_strategique"] = {}
        for objectif in objectifs_tous:
            aggregates["by_objectif_strategique"][objectif] = _resume(
                df[df[cols["objectif_strat"]] == objectif], cols
            )

    # Croisements : clé "a|b" plutôt qu'un dict imbriqué, pour rester à plat en
    # JSON. Seuls les couples non vides sont écrits.
    aggregates["by_region_fonds"] = {}
    for region in regions_mono:
        for fonds in fonds_tous:
            subset = df_mono_region[
                (region_principale == region) & (df_mono_region[cols["fonds"]] == fonds)
            ]
            if len(subset) > 0:
                aggregates["by_region_fonds"][f"{region}|{fonds}"] = {
                    "region": region,
                    "fonds": fonds,
                    "count": len(subset),
                    "montant_ue_total": float(subset[cols["montant_ue"]].sum()),
                }

    if a_objectif:
        aggregates["by_region_objectif"] = {}
        for region in regions_mono:
            for objectif in objectifs_tous:
                subset = df_mono_region[
                    (region_principale == region) & (df_mono_region[cols["objectif_strat"]] == objectif)
                ]
                if len(subset) > 0:
                    aggregates["by_region_objectif"][f"{region}|{objectif}"] = {
                        "region": region,
                        "objectif_strategique": objectif,
                        "count": len(subset),
                        "montant_ue_total": float(subset[cols["montant_ue"]].sum()),
                    }

        aggregates["by_fonds_objectif"] = {}
        for fonds in fonds_tous:
            for objectif in objectifs_tous:
                subset = df[(df[cols["fonds"]] == fonds) & (df[cols["objectif_strat"]] == objectif)]
                if len(subset) > 0:
                    aggregates["by_fonds_objectif"][f"{fonds}|{objectif}"] = {
                        "fonds": fonds,
                        "objectif_strategique": objectif,
                        "count": len(subset),
                        "montant_ue_total": float(subset[cols["montant_ue"]].sum()),
                    }

    return aggregates
