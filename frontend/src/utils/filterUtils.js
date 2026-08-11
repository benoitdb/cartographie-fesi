/**
 * Filtre les agrégats basé sur les fonds sélectionnés
 */
export function applyFilters(aggregates, filters) {
  if (!filters || !aggregates) return aggregates

  const { fonds = ['FEDER', 'FSE+', 'FTJ'] } = filters

  // Copier les agrégats complets
  const filtered = JSON.parse(JSON.stringify(aggregates))

  // Filtrer by_fonds : garder seulement les fonds sélectionnés
  if (filtered.by_fonds) {
    const selectedFonds = {}
    fonds.forEach(fond => {
      if (filtered.by_fonds[fond]) {
        selectedFonds[fond] = filtered.by_fonds[fond]
      }
    })
    filtered.by_fonds = selectedFonds
  }

  return filtered
}
