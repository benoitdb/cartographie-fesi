import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from region_mapping import harmonize_region

# Chemins
XLSX_PATH = Path(__file__).parent.parent / "data" / "raw" / "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_DIR.mkdir(exist_ok=True)

# Lire le fichier
print("📖 Lecture du fichier XLSX...")
df = pd.read_excel(XLSX_PATH, sheet_name=0)

print(f"✅ Données chargées: {len(df)} opérations")

# Créer un mapping des colonnes par index (plus fiable que les noms)
col_list = list(df.columns)
COLS = {
    'numero_op': col_list[0],          # Numéro Opération
    'numcci': col_list[1],             # NUMCCI
    'libelle_prog': col_list[2],       # Libellé Programme
    'intitule_proj': col_list[3],      # Intitulé du projet
    'objectifs_desc': col_list[4],     # Objectifs et réalisations escomptés et effectifs
    'nom_benef': col_list[5],          # Nom du bénéficiaire
    'cp_beneficiaire': col_list[6],    # Code postal du bénéficiaire
    'date_debut': col_list[7],         # Date de début de l'opération
    'date_fin': col_list[8],           # Date de fin de l'opération
    'cp_operation': col_list[9],       # Code postal de l'opération
    'zone': col_list[10],              # Zone
    'departement': col_list[11],       # Département de l'opération
    'region': col_list[12],            # Région de l'opération
    'pays': col_list[13],              # Pays
    'type_intervention': col_list[14], # Type d'intervention
    'fonds': col_list[15],             # Fonds
    'objectif_spec': col_list[16],     # Objectif spécifique
    'objectif_spec_lib': col_list[17], # Objectif spécifique (Code et libellé)
    'objectif_strat': col_list[18],    # Objectif stratégique
    'depenses': col_list[19],          # Total des dépenses éligibles
    'taux_cofinance': col_list[20],    # Taux de cofinancement
    'montant_ue': col_list[21],        # Montant UE
    'date_convention': col_list[22],   # Date première convention
}

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

# Exporter les opérations brutes
print("💾 Export des opérations brutes...")
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

with open(OUTPUT_DIR / "operations.json", 'w', encoding='utf-8') as f:
    json.dump(operations, f, ensure_ascii=False, indent=2)

# Calculer les agrégats (respecte la structure : by_region, national, interregional, etc.)
print("📊 Calcul des agrégats harmonisés...")

aggregates = {}

# Partitionner les données selon le type de région
df_mono_region = df[~df['is_interregional'] & ~df['is_national']]
df_interregional = df[df['is_interregional']]
df_national = df[df['is_national']]

print(f"  Partitions : mono-région={len(df_mono_region)} | interrég={len(df_interregional)} | national={len(df_national)}")

# === by_region : uniquement opérations mono-région ===
print("  - Agrégats par région (mono-région uniquement)...")
aggregates['by_region'] = {}
for region in sorted(df_mono_region['regions_modernes'].apply(lambda x: x[0] if x else None).dropna().unique()):
    subset = df_mono_region[df_mono_region['regions_modernes'].apply(lambda x: (x[0] if x else None) == region)]
    if len(subset) > 0:
        aggregates['by_region'][region] = {
            'count': int(len(subset)),
            'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            'montant_ue_moyen': float(subset[COLS['montant_ue']].mean()),
            'depenses_total': float(subset[COLS['depenses']].sum()),
            'depenses_moyen': float(subset[COLS['depenses']].mean()),
        }

# === national : opérations sans région ===
print("  - Agrégat national...")
if len(df_national) > 0:
    aggregates['national'] = {
        'count': int(len(df_national)),
        'montant_ue_total': float(df_national[COLS['montant_ue']].sum()),
        'montant_ue_moyen': float(df_national[COLS['montant_ue']].mean()),
        'depenses_total': float(df_national[COLS['depenses']].sum()),
        'depenses_moyen': float(df_national[COLS['depenses']].mean()),
    }

# === interregional : opérations multi-régions ===
print("  - Agrégat interrégional...")
if len(df_interregional) > 0:
    aggregates['interregional'] = {
        'count': int(len(df_interregional)),
        'montant_ue_total': float(df_interregional[COLS['montant_ue']].sum()),
        'montant_ue_moyen': float(df_interregional[COLS['montant_ue']].mean()),
        'depenses_total': float(df_interregional[COLS['depenses']].sum()),
        'depenses_moyen': float(df_interregional[COLS['depenses']].mean()),
        'operations': [row[COLS['numero_op']] for _, row in df_interregional.iterrows()]
    }

# === by_fonds : sur toutes les opérations ===
print("  - Agrégats par fonds...")
aggregates['by_fonds'] = {}
for fonds in sorted(df[COLS['fonds']].unique()):
    subset = df[df[COLS['fonds']] == fonds]
    aggregates['by_fonds'][fonds] = {
        'count': int(len(subset)),
        'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
        'montant_ue_moyen': float(subset[COLS['montant_ue']].mean()),
        'depenses_total': float(subset[COLS['depenses']].sum()),
        'depenses_moyen': float(subset[COLS['depenses']].mean()),
    }

# === by_objectif_strategique : sur toutes les opérations ===
print("  - Agrégats par objectif stratégique...")
aggregates['by_objectif_strategique'] = {}
for obj in sorted(df[COLS['objectif_strat']].dropna().unique()):
    subset = df[df[COLS['objectif_strat']] == obj]
    aggregates['by_objectif_strategique'][obj] = {
        'count': int(len(subset)),
        'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
        'montant_ue_moyen': float(subset[COLS['montant_ue']].mean()),
        'depenses_total': float(subset[COLS['depenses']].sum()),
        'depenses_moyen': float(subset[COLS['depenses']].mean()),
    }

# === by_region_fonds : uniquement mono-région ===
print("  - Croisements région × fonds...")
aggregates['by_region_fonds'] = {}
for region in sorted(df_mono_region['regions_modernes'].apply(lambda x: x[0] if x else None).dropna().unique()):
    for fonds in sorted(df[COLS['fonds']].unique()):
        subset = df_mono_region[
            (df_mono_region['regions_modernes'].apply(lambda x: (x[0] if x else None) == region)) &
            (df_mono_region[COLS['fonds']] == fonds)
        ]
        if len(subset) > 0:
            key = f"{region}|{fonds}"
            aggregates['by_region_fonds'][key] = {
                'region': region,
                'fonds': fonds,
                'count': int(len(subset)),
                'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            }

# === by_region_objectif : uniquement mono-région ===
print("  - Croisements région × objectif stratégique...")
aggregates['by_region_objectif'] = {}
for region in sorted(df_mono_region['regions_modernes'].apply(lambda x: x[0] if x else None).dropna().unique()):
    for obj in sorted(df[COLS['objectif_strat']].dropna().unique()):
        subset = df_mono_region[
            (df_mono_region['regions_modernes'].apply(lambda x: (x[0] if x else None) == region)) &
            (df_mono_region[COLS['objectif_strat']] == obj)
        ]
        if len(subset) > 0:
            key = f"{region}|{obj}"
            aggregates['by_region_objectif'][key] = {
                'region': region,
                'objectif_strategique': obj,
                'count': int(len(subset)),
                'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            }

# === by_fonds_objectif : sur toutes les opérations ===
print("  - Croisements fonds × objectif stratégique...")
aggregates['by_fonds_objectif'] = {}
for fonds in sorted(df[COLS['fonds']].unique()):
    for obj in sorted(df[COLS['objectif_strat']].dropna().unique()):
        subset = df[(df[COLS['fonds']] == fonds) & (df[COLS['objectif_strat']] == obj)]
        if len(subset) > 0:
            key = f"{fonds}|{obj}"
            aggregates['by_fonds_objectif'][key] = {
                'fonds': fonds,
                'objectif_strategique': obj,
                'count': int(len(subset)),
                'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            }

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
            'mono_region': int(len(df_mono_region)),
            'interregional': int(len(df_interregional)),
            'national': int(len(df_national)),
        }
    },
    'operations': operations,
    'aggregates': aggregates,
}

with open(OUTPUT_DIR / "data.json", 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("\n✅ Pipeline terminé !")
print(f"   📁 Fichiers générés dans: {OUTPUT_DIR}")
print(f"   - operations.json ({len(operations)} opérations)")
print(f"   - data.json (opérations + agrégats harmonisés)")
print(f"\n📊 Résumé harmonisé:")
print(f"   Régions harmonisées: {len(aggregates['by_region'])} (brutes: {df[COLS['region']].nunique()})")
print(f"   Fonds: {df[COLS['fonds']].nunique()}")
print(f"   Objectifs stratégiques: {df[COLS['objectif_strat']].nunique()}")
print(f"   Partitions:")
print(f"     - Mono-région: {len(df_mono_region)}")
print(f"     - Interrégional: {len(df_interregional)}")
print(f"     - National (Volet national): {len(df_national)}")
print(f"   Montant UE total: €{df[COLS['montant_ue']].sum():,.0f}")
print(f"     - Mono-région: €{df_mono_region[COLS['montant_ue']].sum():,.0f}")
print(f"     - Interrégional: €{df_interregional[COLS['montant_ue']].sum():,.0f}")
print(f"     - National: €{df_national[COLS['montant_ue']].sum():,.0f}")
