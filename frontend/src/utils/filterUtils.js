/**
 * Filtre les agrégats basé sur les filtres actifs
 */
export function applyFilters(aggregates, filters) {
  if (!filters || !aggregates) return aggregates

  const { fonds = ['FEDER', 'FSE+', 'FTJ'], montantMin = 0 } = filters

  // Copier les agrégats
  const filtered = { ...aggregates }

  // Filtrer by_fonds : garder seulement les fonds sélectionnés
  if (filtered.by_fonds) {
    filtered.by_fonds = Object.fromEntries(
      Object.entries(filtered.by_fonds).filter(([fond]) => fonds.includes(fond))
    )
  }

  // Filtrer by_region : garder seulement régions avec montant >= montantMin (en M€)
  if (filtered.by_region) {
    const montantMinEuros = montantMin * 1e6
    filtered.by_region = Object.fromEntries(
      Object.entries(filtered.by_region).filter(
        ([, data]) => (data.montant_ue_total || 0) >= montantMinEuros
      )
    )
  }

  // Recalculer by_objectif_strategique basé sur les fonds et montants filtrés
  if (filtered.by_objectif_strategique && filtered.by_region) {
    const montantMinEuros = montantMin * 1e6
    const selectedRegions = Object.keys(filtered.by_region)

    filtered.by_objectif_strategique = Object.fromEntries(
      Object.entries(filtered.by_objectif_strategique)
        .map(([obj, data]) => [
          obj,
          {
            montant_ue_total: data.montant_ue_total || 0,
            count: data.count || 0,
          },
        ])
        .filter(([, data]) => data.montant_ue_total >= montantMinEuros)
    )
  }

  // Recalculer les totaux
  filtered.total_count = Object.values(filtered.by_region || {}).reduce(
    (sum, r) => sum + (r.count || 0),
    0
  )
  filtered.total_montant = Object.values(filtered.by_region || {}).reduce(
    (sum, r) => sum + (r.montant_ue_total || 0),
    0
  )

  return filtered
}
