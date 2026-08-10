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
        radialLabelsTextColor="#000"
        radialLabelsTextStrokeWidth={2}
        radialLabelsTextStroke="#fff"
        slicesLabelsSkipAngle={10}
        slicesLabelsTextColor={{ from: 'color', modifiers: [['darker', 2.5]] }}
        animate={true}
        motionConfig="gentle"
        tooltip={({ id, value }) => (
          <div
            style={{
              background: 'white',
              padding: '12px 16px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              minWidth: '220px',
              whiteSpace: 'normal',
              wordWrap: 'break-word'
            }}
          >
            <strong style={{ display: 'block', marginBottom: '6px' }}>{id}</strong>
            <span style={{ fontSize: '1.1em', fontWeight: 'bold', color: '#1f8fb0' }}>
              {formatCurrency(value)}
            </span>
          </div>
        )}
        isInteractive={true}
      />
    </div>
  )
}

export default ObjectifsSunburst
