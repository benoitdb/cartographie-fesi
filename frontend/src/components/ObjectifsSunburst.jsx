import { ResponsiveSunburst } from '@nivo/sunburst'
import { formatCurrency } from '../utils/colorScale'

function ObjectifsSunburst({ hierarchyData }) {
  if (!hierarchyData || !hierarchyData.children || hierarchyData.children.length === 0) {
    return <div className="chart-error">Pas de données disponibles</div>
  }

  return (
    <div className="chart-container sunburst-container">
      <h3>Objectifs stratégiques (cliquez pour zoomer)</h3>
      <ResponsiveSunburst
        data={hierarchyData}
        margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
        id="id"
        value="value"
        colors={{ scheme: 'blues' }}
        borderWidth={2}
        borderColor={{ from: 'color', modifiers: [['darker', 0.3]] }}
        radialLabelsSkipAngle={10}
        radialLabelsTextXOffset={6}
        radialLabelsTextColor="#333"
        slicesLabelsSkipAngle={10}
        slicesLabelsTextColor="#fff"
        animate={true}
        motionConfig="gentle"
        tooltip={({ id, value }) => (
          <div
            style={{
              background: 'white',
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid #ccc'
            }}
          >
            <strong>{id}</strong>
            <br />
            {formatCurrency(value)}
          </div>
        )}
        isInteractive={true}
      />
    </div>
  )
}

export default ObjectifsSunburst
