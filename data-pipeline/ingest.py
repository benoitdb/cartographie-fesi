"""XLSX source → JSON servi au dashboard, une sortie par source.

Un seul pipeline, paramétré par source (arbitrage 3 de l'issue #12) : ce qui
diffère entre 2014-2020 et 2021-2027, ce sont des **données** — quel fichier,
quelle feuille, quel schéma, quelle table programme → région, dimension
thématique ou non — pas de la logique. Un second script pour 14-20 dupliquerait
justement ce qu'il ne faut pas dupliquer : `agregats.calculer_agregats`, seul
endroit où se calculent les totaux servis au dashboard (le dupliquer reprendrait
le défaut corrigé par #60 et garantirait la divergence des deux copies),
`harmonize_region` et ses tables, la normalisation des codes postaux, le
garde-fou de schéma, la trace du millésime.

Usage :
    python ingest.py                          # défaut : 2021-2027 → data.json
    python ingest.py 2014-2020-synergie        #          → data_2014-2020.json
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from agregats import calculer_agregats, partitionner
from region_mapping import (
    get_unresolved,
    harmonize_region,
    indexer_programmes,
    reset_unresolved,
)
from schema_source import SchemaSourceError
from sources import cols_internes, millesime, source, trouver_fichier

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"

SOURCE_PAR_DEFAUT = "2021-2027-conventionnees"


def prepare_for_json(df):
    """Convertir les types non-sérialisables en types JSON-compatibles"""
    df_copy = df.copy()
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')
        elif pd.api.types.is_float_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].round(2)
        # Remplacer NaN par None pour JSON
        df_copy[col] = df_copy[col].where(pd.notna(df_copy[col]), None)
    return df_copy


def clean_nans(obj):
    """Nettoyer les NaN qui auraient échappé à la conversion"""
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(v) for v in obj]
    elif isinstance(obj, float) and pd.isna(obj):
        return None
    return obj


def harmoniser_regions(df, cols, programme_index):
    """Pose les colonnes `regions_modernes` / `is_interregional` / `is_national`.

    L'index programme → région est celui de la **période** : en 2014-2020 la
    colonne région n'est remplie qu'à 16,4 %, et c'est le libellé du programme
    qui rattache les 83,6 % restantes (issue #12).
    """
    reset_unresolved()

    def apply_harmonize(row):
        regions_modernes, is_interregional, is_national = harmonize_region(
            row[cols['region']],
            row[cols['libelle_prog']],
            programme_index,
        )
        return pd.Series({
            'regions_modernes': regions_modernes,
            'is_interregional': is_interregional,
            'is_national': is_national,
            'regions_source': str(row[cols['region']]) if pd.notna(row[cols['region']]) else None
        })

    harmonization = df.apply(apply_harmonize, axis=1)
    df = pd.concat([df, harmonization], axis=1)

    unresolved = get_unresolved()
    if unresolved:
        print(f"⚠️  {len(unresolved)} fragment(s) région non résolu(s) par code ni par nom (repli sur le nom brut) :")
        for fragment, count in Counter(unresolved).most_common():
            print(f"     - {fragment!r} (x{count})")
    else:
        print("✅ Tous les fragments région résolus (code ou nom reconnu).")

    return df


def construire_metadata(df, cols, conf, chemin, aggregates, partitions):
    """Bloc `metadata` de la sortie.

    `nb_objectifs_strategiques` n'est écrit **que** si la période porte cette
    dimension. Pour 2014-2020 elle est remplacée par `dimension_thematique: None`,
    déclaré explicitement : sa colonne `Domaine d'intervention` est vide à 100 %
    dans le fichier Synergie (issues #12, #73). Une catégorie « Non spécifié »
    inventée ferait croire à une dimension mesurée et vide, alors qu'elle est
    absente de la source.
    """
    metadata = {
        'generated_at': datetime.now().isoformat(),
        # Millésime du fichier source, propagé jusqu'au dashboard qui l'affiche :
        # la source est republiée 5 fois par an, la fraîcheur des chiffres doit se
        # lire à l'écran et pas seulement dans le log du pipeline (issue #47).
        'fichier_source': chemin.name,
        # Date déclarée par la source si elle en a une (le fichier Synergie
        # 14-20 n'a pas de préfixe daté), sinon le préfixe du nom de fichier.
        'millesime': millesime(conf, chemin),
        'periode': conf['periode'],
        'total_operations': len(df),
        'nb_regions_harmonized': len(aggregates['by_region']),
        'nb_regions_raw': df[cols['region']].nunique(),
        'nb_fonds': df[cols['fonds']].nunique(),
    }

    if 'objectif_strat' in cols:
        metadata['nb_objectifs_strategiques'] = df[cols['objectif_strat']].nunique()
    else:
        metadata['dimension_thematique'] = None

    metadata['partitions'] = {
        'mono_region': len(partitions.mono_region),
        'interregional': len(partitions.interregional),
        'national': len(partitions.national),
    }
    return metadata


def main(source_id=SOURCE_PAR_DEFAUT):
    conf = source(source_id)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Millésime le plus récent, pas un chemin codé en dur : le fichier 2021-2027
    # est republié 5 fois par an en « annule et remplace » (issue #47).
    chemin = trouver_fichier(conf)

    print(f"📖 Lecture du fichier XLSX : {chemin.name}")
    # Feuille déclarée par la source : celle du fichier Synergie est la **2ᵉ**,
    # sa feuille 0 étant une notice — lire l'index 0 par défaut y produirait un
    # DataFrame de notice, sans la moindre erreur.
    df = pd.read_excel(chemin, sheet_name=conf['feuille'])

    print(f"✅ Données chargées: {len(df)} opérations")

    # Mapping des colonnes par index (plus fiable que les noms), mais vérifié
    # contre les libellés attendus de la période : sans ce contrôle, un
    # réordonnancement du fichier source produirait des données fausses sans
    # erreur (issue #45).
    cols = cols_internes(conf, df.columns)

    # Convertir les colonnes de codes postaux en string et nettoyer
    print("🔄 Normalisation des données...")
    df[cols['cp_beneficiaire']] = df[cols['cp_beneficiaire']].astype(str).str.replace('.0', '', regex=False)
    df[cols['cp_operation']] = df[cols['cp_operation']].astype(str).str.strip()

    # Remplacer les 'nan' string par NaN
    for col in df.columns:
        if df[col].dtype == 'object':
            df.loc[df[col] == 'nan', col] = None

    # Harmoniser les régions avec la fonction de mapping
    print("🌍 Harmonisation des régions (pré-2016 → modernes)...")
    # Table de la période, indexée **une fois** : `harmonize_region` est appelée
    # une fois par opération. Passée explicitement même pour 2021-2027, où c'est
    # déjà le défaut — l'implicite rattacherait toute la période 14-20 au Volet
    # national sans lever d'erreur.
    df = harmoniser_regions(df, cols, indexer_programmes(conf['programme_to_region']))

    df_json = prepare_for_json(df)

    # Opérations sérialisables, reprises telles quelles dans la sortie plus bas.
    #
    # Elles étaient aussi écrites à part dans operations.json, retiré (issue #46) :
    # 44 Mo par régénération pour un fichier que personne ne lisait. Ce n'était pas
    # un vestige du prototype React — il est né avec le dépôt (commit initial, qui ne
    # contenait que le pipeline), data.json embarquait déjà la même liste dès ce
    # commit, et le frontend chargeait data.json, jamais celui-ci. Un doublon dès la
    # première ligne, donc, pas un usage disparu : rien à restaurer si la question
    # se repose.
    print("🧹 Préparation des opérations...")
    operations = clean_nans(df_json.to_dict(orient='records'))

    # Calcul délégué à agregats.py : il était écrit à plat ici, dépendant des
    # variables globales de ce script, donc ni testable ni rejouable sur un
    # sous-ensemble (issue #60).
    print("📊 Calcul des agrégats harmonisés...")
    partitions = partitionner(df)
    print(
        f"  Partitions : mono-région={len(partitions.mono_region)} | "
        f"interrég={len(partitions.interregional)} | national={len(partitions.national)}"
    )
    aggregates = clean_nans(calculer_agregats(df, cols, partitions))

    # Créer le fichier final
    print("💾 Création du fichier de sortie...")
    output_data = {
        'metadata': construire_metadata(df, cols, conf, chemin, aggregates, partitions),
        'operations': operations,
        'aggregates': aggregates,
    }

    sortie = OUTPUT_DIR / conf['fichier_sortie']
    with open(sortie, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    resumer(df, cols, aggregates, partitions, sortie, operations)


def resumer(df, cols, aggregates, partitions, sortie, operations):
    """Résumé lu à l'œil après chaque régénération : c'est là qu'un écart de
    volume ou de montant se voit avant que le dashboard ne l'affiche."""
    print("\n✅ Pipeline terminé !")
    print(f"   📁 Fichiers générés dans: {OUTPUT_DIR}")
    print(f"   - {sortie.name} ({len(operations)} opérations + agrégats harmonisés)")
    print("\n📊 Résumé harmonisé:")
    print(f"   Régions harmonisées: {len(aggregates['by_region'])} (brutes: {df[cols['region']].nunique()})")
    print(f"   Fonds: {df[cols['fonds']].nunique()}")
    if 'objectif_strat' in cols:
        print(f"   Objectifs stratégiques: {df[cols['objectif_strat']].nunique()}")
    else:
        print("   Dimension thématique: absente de cette source")
    print("   Partitions:")
    print(f"     - Mono-région: {len(partitions.mono_region)}")
    print(f"     - Interrégional: {len(partitions.interregional)}")
    print(f"     - National (Volet national): {len(partitions.national)}")
    print(f"   Montant UE total: €{df[cols['montant_ue']].sum():,.0f}")
    print(f"     - Mono-région: €{partitions.mono_region[cols['montant_ue']].sum():,.0f}")
    print(f"     - Interrégional: €{partitions.interregional[cols['montant_ue']].sum():,.0f}")
    print(f"     - National: €{partitions.national[cols['montant_ue']].sum():,.0f}")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else SOURCE_PAR_DEFAUT)
    except SchemaSourceError as erreur:
        raise SystemExit(str(erreur)) from erreur
