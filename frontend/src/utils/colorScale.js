/**
 * Calcule une échelle de couleurs séquentielle (bleu) basée sur les montants UE par région.
 * Utilise des quantiles simples sans dépendance externe.
 */

export function getColorScale(aggregatesByRegion) {
  // Extraire les montants (exclure les régions manquantes)
  const amounts = Object.values(aggregatesByRegion || {})
    .map(agg => agg.montant_ue_total)
    .filter(x => x && x > 0)
    .sort((a, b) => a - b)

  if (amounts.length === 0) {
    return () => '#e8f4f8' // gris clair par défaut
  }

  // Calculer les quantiles (5 niveaux)
  const min = amounts[0]
  const max = amounts[amounts.length - 1]

  const q25 = amounts[Math.floor(amounts.length * 0.25)]
  const q50 = amounts[Math.floor(amounts.length * 0.50)]
  const q75 = amounts[Math.floor(amounts.length * 0.75)]

  // Palette séquentielle bleu (clair → foncé)
  const colors = [
    '#eff8fb', // très clair (min)
    '#a8d9ea', // clair
    '#5cb8dc', // moyen
    '#1f8fb0', // foncé
    '#0d5a78'  // très foncé (max)
  ]

  return (value) => {
    if (!value || value <= 0) return colors[0]
    if (value <= q25) return colors[0]
    if (value <= q50) return colors[1]
    if (value <= q75) return colors[2]
    if (value < max) return colors[3]
    return colors[4]
  }
}

export function formatCurrency(value) {
  if (!value || value === 0) return '€0'
  if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B€'
  if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M€'
  if (value >= 1e3) return (value / 1e3).toFixed(1) + 'k€'
  return value.toFixed(0) + '€'
}
