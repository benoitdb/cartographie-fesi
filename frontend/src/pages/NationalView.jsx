import { useData } from '../hooks/useData'
import Map from '../components/Map'
import StatsGrid from '../components/StatsGrid'
import FondsChart from '../components/FondsChart'
import TopRegionsChart from '../components/TopRegionsChart'
import ObjectifsSunburst from '../components/ObjectifsSunburst'
import { objectifStrategiqueToSunburst } from '../utils/chartData'
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

      <div className="section">
        <Map
          data={data}
          selectedRegion={null}
          onRegionSelect={onRegionSelect}
        />
      </div>

      <div className="section">
        <h3>Statistiques nationales</h3>
        <StatsGrid aggregates={data.aggregates} />

        {/* Volet national + Interrégional */}
        <div className="special-aggregates">
          {data.aggregates.national && (
            <div className="aggregate-card">
              <div className="aggregate-title">📋 Volet National</div>
              <div className="aggregate-stat">
                <span>{data.aggregates.national.count} projets</span>
                <span>
                  €{(data.aggregates.national.montant_ue_total / 1e6).toFixed(1)}M
                </span>
              </div>
            </div>
          )}

          {data.aggregates.interregional && (
            <div className="aggregate-card">
              <div className="aggregate-title">🌍 Interrégional</div>
              <div className="aggregate-stat">
                <span>{data.aggregates.interregional.count} projets</span>
                <span>
                  €{(data.aggregates.interregional.montant_ue_total / 1e6).toFixed(1)}M
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Graphiques */}
      <div className="charts-section">
        <div className="chart-row">
          <div className="chart-half">
            <FondsChart byFonds={data.aggregates.by_fonds} />
          </div>
          <div className="chart-half">
            <ObjectifsSunburst hierarchyData={objectifStrategiqueToSunburst(data.aggregates.by_objectif_strategique)} />
          </div>
        </div>
        <div className="chart-full">
          <TopRegionsChart byRegion={data.aggregates.by_region} />
        </div>
      </div>
    </div>
  )
}

export default NationalView
