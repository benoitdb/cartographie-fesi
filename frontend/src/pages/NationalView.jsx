import { useData } from '../hooks/useData'
import { useRegion } from '../context/RegionContext'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import FondsChart from '../components/FondsChart'
import TopRegionsChart from '../components/TopRegionsChart'
import ObjectifsSunburst from '../components/ObjectifsSunburst'
import { objectifStrategiqueToSunburst, formatCurrency } from '../utils/chartData'

function NationalView() {
  const { data } = useData()
  const { selectRegion } = useRegion()

  if (!data) return <div className="py-8 text-center">Chargement...</div>

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="border-b border-gray-200 dark:border-gray-800 pb-6">
        <h2 className="text-3xl font-bold font-sans mb-2">Vue Nationale</h2>
        <p className="text-gray-600 dark:text-gray-400">Cliquez sur une région pour voir les détails</p>
      </div>

      {/* Map + Stats Grid côte à côte */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Carte - 3 colonnes */}
        <div className="lg:col-span-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md overflow-hidden">
          <Map
            data={data}
            selectedRegion={null}
            onRegionSelect={selectRegion}
          />
        </div>

        {/* Stats - 2 colonnes */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
            <h3 className="text-xl font-bold font-sans mb-4">Statistiques nationales</h3>
            <StatsGrid aggregates={data.aggregates} />
          </div>

          {/* Volet national + Interrégional */}
          <div className="flex flex-col gap-3">
            {data.aggregates.national && (
              <div className="bg-gradient-to-br from-orange-500 to-orange-600 dark:from-orange-700 dark:to-orange-800 text-white rounded-xl p-4 shadow-md">
                <div className="text-sm font-medium opacity-90 mb-2">📋 Volet National</div>
                <div className="flex justify-between items-end">
                  <span className="text-2xl font-bold">{data.aggregates.national.count}</span>
                  <span className="text-sm opacity-95">projets</span>
                </div>
                <div className="mt-3 pt-3 border-t border-orange-400 border-opacity-30">
                  <span className="text-xl font-bold">€{(data.aggregates.national.montant_ue_total / 1e6).toFixed(1)}M</span>
                </div>
              </div>
            )}

            {data.aggregates.interregional && (
              <div className="bg-gradient-to-br from-cyan-500 to-cyan-600 dark:from-cyan-700 dark:to-cyan-800 text-white rounded-xl p-4 shadow-md">
                <div className="text-sm font-medium opacity-90 mb-2">🌍 Interrégional</div>
                <div className="flex justify-between items-end">
                  <span className="text-2xl font-bold">{data.aggregates.interregional.count}</span>
                  <span className="text-sm opacity-95">projets</span>
                </div>
                <div className="mt-3 pt-3 border-t border-cyan-400 border-opacity-30">
                  <span className="text-xl font-bold">€{(data.aggregates.interregional.montant_ue_total / 1e6).toFixed(1)}M</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Graphiques */}
      <div className="flex flex-col gap-8">
        {/* Charts 2 colonnes */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
            <FondsChart byFonds={data.aggregates.by_fonds} />
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
            <ObjectifsSunburst hierarchyData={objectifStrategiqueToSunburst(data.aggregates.by_objectif_strategique)} />
          </div>
        </div>

        {/* Top regions - full width */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
          <TopRegionsChart byRegion={data.aggregates.by_region} />
        </div>
      </div>
    </div>
    </div>
  )
}

export default NationalView
