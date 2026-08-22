import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from agregats import calculer_agregats, partitionner
from region_mapping import get_unresolved, harmonize_region, reset_unresolved
from schema_source import build_cols, trouver_fichier_source

# Chemins
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_DIR.mkdir(exist_ok=True)

# Millésime le plus récent, pas un chemin codé en dur : le fichier est republié
# 5 fois par an en « annule et remplace » (issue #47).
XLSX_PATH = trouver_fichier_source(RAW_DIR)

# Lire le fichier
print(f"📖 Lecture du fichier XLSX : {XLSX_PATH.name}")
df = pd.read_excel(XLSX_PATH, sheet_name=0)

print(f"✅ Données chargées: {len(df)} opérations")

# Mapping des colonnes par index (plus fiable que les noms), mais vérifié contre
# les libellés attendus : sans ce contrôle, un réordonnancement du fichier source
# produirait des données fausses sans erreur (issue #45).
COLS = build_cols(df.columns)

# Convertir les colonnes de codes postaux en string et nettoyer
print("🔄 Normalisation des données...")
df[COLS['cp_beneficiaire']] = df[COLS['cp_beneficiaire']].astype(str).str.replace('.0', '', regex=False)
df[COLS['cp_operation']] = df[COLS['cp_operation']].astype(str).str.strip()

# Remplacer les 'nan' string par NaN
for col in df.columns:
    if df[col].dtype == 'object':
        df.loc[df[col] == 'nan', col] = None

# Harmoniser les régions avec la fonction de mapping
print("🌍 Harmonisation des régions (pré-2016 → modernes)...")
reset_unresolved()
def apply_harmonize(row):
    regions_modernes, is_interregional, is_national = harmonize_region(
        row[COLS['region']],
        row[COLS['libelle_prog']]
    )
    return pd.Series({
        'regions_modernes': regions_modernes,
        'is_interregional': is_interregional,
        'is_national': is_national,
        'regions_source': str(row[COLS['region']]) if pd.notna(row[COLS['region']]) else None
    })

harmonization = df.apply(apply_harmonize, axis=1)
df = pd.concat([df, harmonization], axis=1)

unresolved = get_unresolved()
if unresolved:
    from collections import Counter
    print(f"⚠️  {len(unresolved)} fragment(s) région non résolu(s) par code ni par nom (repli sur le nom brut) :")
    for fragment, count in Counter(unresolved).most_common():
        print(f"     - {fragment!r} (x{count})")
else:
    print("✅ Tous les fragments région résolus (code ou nom reconnu).")

# Préparer les données pour JSON
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

df_json = prepare_for_json(df)

# Opérations sérialisables, reprises telles quelles dans data.json plus bas.
#
# Elles étaient aussi écrites à part dans operations.json, retiré (issue #46) :
# 44 Mo par régénération pour un fichier que personne ne lisait. Ce n'était pas
# un vestige du prototype React — il est né avec le dépôt (commit initial, qui ne
# contenait que le pipeline), data.json embarquait déjà la même liste dès ce
# commit, et le frontend chargeait data.json, jamais celui-ci. Un doublon dès la
# première ligne, donc, pas un usage disparu : rien à restaurer si la question
# se repose.
print("🧹 Préparation des opérations...")
operations = df_json.to_dict(orient='records')

# Nettoyer les NaN qui auraient échappé à la conversion
def clean_nans(obj):
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(v) for v in obj]
    elif isinstance(obj, float) and pd.isna(obj):
        return None
    return obj

operations = clean_nans(operations)

# Calcul délégué à agregats.py : il était écrit à plat ici, dépendant des
# variables globales de ce script, donc ni testable ni rejouable sur un
# sous-ensemble (issue #60).
print("📊 Calcul des agrégats harmonisés...")
partitions = partitionner(df)
print(
    f"  Partitions : mono-région={len(partitions.mono_region)} | "
    f"interrég={len(partitions.interregional)} | national={len(partitions.national)}"
)
aggregates = calculer_agregats(df, COLS, partitions)

# Créer le fichier final
print("💾 Création du fichier de sortie...")

# Nettoyer les agrégats aussi
aggregates = clean_nans(aggregates)

output_data = {
    'metadata': {
        'generated_at': datetime.now().isoformat(),
        'total_operations': len(df),
        'nb_regions_harmonized': len(aggregates['by_region']),
        'nb_regions_raw': df[COLS['region']].nunique(),
        'nb_fonds': df[COLS['fonds']].nunique(),
        'nb_objectifs_strategiques': df[COLS['objectif_strat']].nunique(),
        'partitions': {
            'mono_region': len(partitions.mono_region),
            'interregional': len(partitions.interregional),
            'national': len(partitions.national),
        }
    },
    'operations': operations,
    'aggregates': aggregates,
}

with open(OUTPUT_DIR / "data.json", 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("\n✅ Pipeline terminé !")
print(f"   📁 Fichiers générés dans: {OUTPUT_DIR}")
print(f"   - data.json ({len(operations)} opérations + agrégats harmonisés)")
print("\n📊 Résumé harmonisé:")
print(f"   Régions harmonisées: {len(aggregates['by_region'])} (brutes: {df[COLS['region']].nunique()})")
print(f"   Fonds: {df[COLS['fonds']].nunique()}")
print(f"   Objectifs stratégiques: {df[COLS['objectif_strat']].nunique()}")
print("   Partitions:")
print(f"     - Mono-région: {len(partitions.mono_region)}")
print(f"     - Interrégional: {len(partitions.interregional)}")
print(f"     - National (Volet national): {len(partitions.national)}")
print(f"   Montant UE total: €{df[COLS['montant_ue']].sum():,.0f}")
print(f"     - Mono-région: €{partitions.mono_region[COLS['montant_ue']].sum():,.0f}")
print(f"     - Interrégional: €{partitions.interregional[COLS['montant_ue']].sum():,.0f}")
print(f"     - National: €{partitions.national[COLS['montant_ue']].sum():,.0f}")
