import { useData } from '../hooks/useData'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
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

      {/* Les graphiques seront ajoutés après */}
      <div className="charts-placeholder">
        Graphiques filtrés par région (Recharts) à venir...
      </div>
    </div>
  )
}

export default RegionalView
