/**
 * Transformations pour formatter les données d'agrégats vers les formats attendus par Recharts/Nivo.
 * Fonctions pures, sans état.
 */

import { formatCurrency } from './colorScale'

export const FONDS_COLORS = {
  FEDER: '#1f77b4',
  'FSE+': '#ff7f0e',
  FTJ: '#2ca02c'
}

export const FONDS_ORDER = ['FEDER', 'FSE+', 'FTJ']

/**
 * Reformate by_fonds (objet d'agrégats) vers format BarChart Recharts
 */
export function fondsToChartData(byFonds) {
  return FONDS_ORDER.map(fonds => {
    const data = byFonds[fonds] || {}
    return {
      fonds,
      montant_ue_total: data.montant_ue_total || 0,
      count: data.count || 0,
      fill: FONDS_COLORS[fonds]
    }
  })
}

/**
 * Reformate by_region (objet d'agrégats) vers format BarChart Recharts horizontal
 */
export function regionsToChartData(byRegion) {
  return Object.entries(byRegion)
    .map(([region, data]) => ({
      region,
      montant_ue_total: data.montant_ue_total || 0,
      count: data.count || 0
    }))
    .sort((a, b) => b.montant_ue_total - a.montant_ue_total)
}

/**
 * Reformate by_objectif_strategique (objet d'agrégats) vers arbre Nivo Sunburst 1 niveau
 */
export function objectifStrategiqueToSunburst(byObjectifStrategique) {
  const children = Object.entries(byObjectifStrategique).map(([objectif, data]) => ({
    id: objectif,
    value: data.montant_ue_total || 0,
    color: data.montant_ue_total || 0 // Nivo colorera par value
  }))

  return {
    id: 'Objectifs Stratégiques',
    children
  }
}

/**
 * Construit arbre Nivo Sunburst 2 niveaux (stratégique → spécifique) à partir des opérations brutes
 * Filtre : uniquement les opérations mono-région qui appartiennent à la région sélectionnée
 */
export function regionalObjectifsToSunburst(operations, selectedRegion) {
  // Filtrer : opérations mono-région de cette région
  const regionalOps = operations.filter(op => {
    const regions = op.regions_modernes || []
    return (
      regions.length === 1 &&
      regions[0] === selectedRegion &&
      !op.is_interregional &&
      !op.is_national
    )
  })

  // Grouper par Objectif stratégique → Objectif spécifique
  const hierarchy = {}

  regionalOps.forEach(op => {
    const strateg = op['Objectif stratégique'] || 'Non spécifié'
    const specific = op['Objectif spécifique (Code et libellé)'] || 'Non spécifié'
    const montant = op['Montant UE'] || 0

    if (!hierarchy[strateg]) {
      hierarchy[strateg] = {}
    }
    if (!hierarchy[strateg][specific]) {
      hierarchy[strateg][specific] = 0
    }

    hierarchy[strateg][specific] += montant
  })

  // Convertir en structure Nivo
  const children = Object.entries(hierarchy).map(([strateg, specifics]) => {
    const specificChildren = Object.entries(specifics).map(([specific, montant]) => ({
      id: specific,
      value: montant
    }))

    const totalMontant = Object.values(specifics).reduce((a, b) => a + b, 0)

    return {
      id: strateg,
      children: specificChildren,
      value: totalMontant // Pour le rendu et le tri
    }
  })

  return {
    id: `${selectedRegion} - Objectifs`,
    children
  }
}

/**
 * Filtre les agrégats by_region_fonds pour une région donnée
 */
export function filtrerFondsParRegion(byRegionFonds, region) {
  const prefix = `${region}|`
  const filtered = {}

  FONDS_ORDER.forEach(fonds => {
    const key = `${prefix}${fonds}`
    if (byRegionFonds[key]) {
      filtered[fonds] = byRegionFonds[key]
    } else {
      filtered[fonds] = { count: 0, montant_ue_total: 0 }
    }
  })

  return filtered
}
