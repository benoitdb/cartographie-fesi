import { useData } from '../hooks/useData'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import FondsChart from '../components/FondsChart'
import ObjectifsSunburst from '../components/ObjectifsSunburst'
import { filtrerFondsParRegion, regionalObjectifsToSunburst } from '../utils/chartData'
import '../styles/views.css'

function RegionalView({ region, onBack }) {
  const { data, getAggregatesByRegion } = useData()
  const regionAggregates = getAggregatesByRegion(region)

  if (!data) return <div>Chargement...</div>

  return (
    <div className="view regional-view">
      <div className="view-header">
        <h2>Vue Régionale: {region}</h2>
        <button className="back-btn" onClick={onBack}>
          ← Retour à la vue nationale
        </button>
      </div>

      <div className="view-grid">
        <div className="section">
          <Map
            data={data}
            selectedRegion={region}
            onRegionSelect={() => {}}
          />
        </div>

        <div className="section">
          {regionAggregates && (
            <StatsGrid aggregates={{ by_region: { [region]: regionAggregates } }} />
          )}
        </div>
      </div>

      {/* Graphiques filtrés par région */}
      <div className="charts-section">
        <div className="chart-row">
          <div className="chart-half">
            <FondsChart byFonds={filtrerFondsParRegion(data.aggregates.by_region_fonds, region)} />
          </div>
          <div className="chart-half">
            <ObjectifsSunburst hierarchyData={regionalObjectifsToSunburst(data.operations, region)} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default RegionalView
