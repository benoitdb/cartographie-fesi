import { useData } from '../hooks/useData'
import { useRegion } from '../context/RegionContext'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import FondsChart from '../components/FondsChart'
import ObjectifsSunburst from '../components/ObjectifsSunburst'
import { filtrerFondsParRegion, regionalObjectifsToSunburst } from '../utils/chartData'

function RegionalView() {
  const { data, getAggregatesByRegion } = useData()
  const { selectedRegion, selectRegion, goToNational } = useRegion()
  const region = selectedRegion
  const regionAggregates = getAggregatesByRegion(region)

  if (!data) return <div className="py-8 text-center">Chargement...</div>

  return (
    <div className="flex flex-col gap-8">
      {/* Header avec bouton retour */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-800 pb-6">
        <div>
          <h2 className="text-3xl font-bold font-sans mb-2">Vue Régionale</h2>
          <p className="text-lg text-primary font-semibold">{region}</p>
        </div>
        <button
          onClick={goToNational}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg font-medium hover:bg-gray-300 dark:hover:bg-gray-700 transition-all"
        >
          ← Retour national
        </button>
      </div>

      {/* Map + Stats côte à côte */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Carte - 3 colonnes */}
        <div className="lg:col-span-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md overflow-hidden">
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

      {/* Graphiques filtrés par région - 2 colonnes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
          <FondsChart byFonds={filtrerFondsParRegion(data.aggregates.by_region_fonds, region)} />
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
          <ObjectifsSunburst hierarchyData={regionalObjectifsToSunburst(data.operations, region)} />
        </div>
      </div>
    </div>
  )
}

export default RegionalView
