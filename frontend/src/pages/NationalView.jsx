import { useData } from '../hooks/useData'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import '../styles/views.css'

function NationalView({ onRegionSelect }) {
  const { data } = useData()

  if (!data) return <div>Chargement...</div>

  return (
    <div className="view national-view">
      <div className="view-header">
        <h2>Vue Nationale</h2>
        <p>Cliquez sur une région pour voir les détails</p>
      </div>

      <div className="view-grid">
        <div className="section">
          <Map
            data={data}
            selectedRegion={null}
            onRegionSelect={onRegionSelect}
          />
        </div>

        <div className="section">
          <StatsGrid aggregates={data.aggregates} />
        </div>
      </div>

      {/* Les graphiques seront ajoutés après */}
      <div className="charts-placeholder">
        Graphiques (Recharts) à venir...
      </div>
    </div>
  )
}

export default NationalView
