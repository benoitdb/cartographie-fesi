import { useData } from '../hooks/useData'
import { useRegion } from '../context/RegionContext'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import FondsChart from '../components/FondsChart'
import ObjectifsGrid from '../components/ObjectifsGrid'
import { filtrerFondsParRegion } from '../utils/chartData'

function RegionalView() {
  const { data, getAggregatesByRegion } = useData()
  const { selectedRegion, selectRegion, goToNational } = useRegion()
  const region = selectedRegion
  const regionAggregates = getAggregatesByRegion(region)

  // Extraire les objectifs stratégiques de la région
  const getRegionalObjectifs = () => {
    if (!data?.operations || !region) return {}

    const regional = data.operations.filter(op => {
      const regions = op.regions_modernes || []
      return regions.length === 1 && regions[0] === region && !op.is_interregional && !op.is_national
    })

    const objectives = {}
    regional.forEach(op => {
      const strateg = op['Objectif stratégique'] || 'Non spécifié'
      if (!objectives[strateg]) {
        objectives[strateg] = { count: 0, montant_ue_total: 0 }
      }
      objectives[strateg].count += 1
      objectives[strateg].montant_ue_total += op['Montant UE'] || 0
    })

    return objectives
  }

  if (!data) return <div className="py-8 text-center">Chargement...</div>

  return (
    <div className="flex flex-col gap-10">
      {/* Header avec bouton retour */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 pb-6">
        <div>
          <h2 className="text-3xl font-bold font-sans mb-2">Vue Régionale</h2>
          <p className="text-lg text-primary font-semibold">{region}</p>
        </div>
        <button
          onClick={goToNational}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg font-medium hover:bg-gray-300 dark:hover:bg-gray-700 transition-all text-sm"
        >
          ← Retour national
        </button>
      </div>

      {/* Map + Stats côte à côte */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Carte - 3 colonnes */}
        <div className="lg:col-span-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-4">
          <Map
            data={data}
            selectedRegion={region}
            onRegionSelect={selectRegion}
          />
        </div>

        {/* Stats - 2 colonnes */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
          {regionAggregates && (
            <StatsGrid aggregates={{ by_region: { [region]: regionAggregates } }} />
          )}
        </div>
      </div>

      {/* Graphiques filtrés par région */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
        <FondsChart byFonds={filtrerFondsParRegion(data.aggregates.by_region_fonds, region)} />
      </div>

      {/* Objectifs Stratégiques */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
        <ObjectifsGrid objectifs={getRegionalObjectifs()} title="Objectifs Stratégiques - Région" />
      </div>
    </div>
  )
}

export default RegionalView
