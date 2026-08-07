import pandas as pd
import json
from pathlib import Path
from datetime import datetime

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

# Normaliser les régions : si manquante, utiliser valeur par défaut
df[COLS['region']] = df[COLS['region']].fillna('Région inconnue')

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
with open(OUTPUT_DIR / "operations.json", 'w', encoding='utf-8') as f:
    json.dump(operations, f, ensure_ascii=False, indent=2)

# Calculer les agrégats
print("📊 Calcul des agrégats...")

aggregates = {}

# Par région
print("  - Agrégats par région...")
aggregates['by_region'] = {}
for region in sorted(df[COLS['region']].unique()):
    subset = df[df[COLS['region']] == region]
    aggregates['by_region'][region] = {
        'count': int(len(subset)),
        'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
        'montant_ue_moyen': float(subset[COLS['montant_ue']].mean()),
        'depenses_total': float(subset[COLS['depenses']].sum()),
        'depenses_moyen': float(subset[COLS['depenses']].mean()),
    }

# Par fonds
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

# Par objectif stratégique
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

# Croisements : région × fonds
print("  - Croisements région × fonds...")
aggregates['by_region_fonds'] = {}
for region in sorted(df[COLS['region']].unique()):
    for fonds in sorted(df[COLS['fonds']].unique()):
        subset = df[(df[COLS['region']] == region) & (df[COLS['fonds']] == fonds)]
        if len(subset) > 0:
            key = f"{region}|{fonds}"
            aggregates['by_region_fonds'][key] = {
                'region': region,
                'fonds': fonds,
                'count': int(len(subset)),
                'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            }

# Croisements : région × objectif stratégique
print("  - Croisements région × objectif stratégique...")
aggregates['by_region_objectif'] = {}
for region in sorted(df[COLS['region']].unique()):
    for obj in sorted(df[COLS['objectif_strat']].dropna().unique()):
        subset = df[(df[COLS['region']] == region) & (df[COLS['objectif_strat']] == obj)]
        if len(subset) > 0:
            key = f"{region}|{obj}"
            aggregates['by_region_objectif'][key] = {
                'region': region,
                'objectif_strategique': obj,
                'count': int(len(subset)),
                'montant_ue_total': float(subset[COLS['montant_ue']].sum()),
            }

# Croisements : fonds × objectif stratégique
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
output_data = {
    'metadata': {
        'generated_at': datetime.now().isoformat(),
        'total_operations': len(df),
        'nb_regions': df[COLS['region']].nunique(),
        'nb_fonds': df[COLS['fonds']].nunique(),
        'nb_objectifs_strategiques': df[COLS['objectif_strat']].nunique(),
    },
    'operations': operations,
    'aggregates': aggregates,
}

with open(OUTPUT_DIR / "data.json", 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("\n✅ Pipeline terminé !")
print(f"   📁 Fichiers générés dans: {OUTPUT_DIR}")
print(f"   - operations.json ({len(operations)} opérations)")
print(f"   - data.json (opérations + agrégats)")
print(f"\n📊 Résumé:")
print(f"   Régions: {df[COLS['region']].nunique()}")
print(f"   Fonds: {df[COLS['fonds']].nunique()}")
print(f"   Objectifs stratégiques: {df[COLS['objectif_strat']].nunique()}")
print(f"   Montant UE total: €{df[COLS['montant_ue']].sum():,.0f}")
