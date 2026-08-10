import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { fondsToChartData, FONDS_COLORS } from '../utils/chartData'
import { formatCurrency } from '../utils/colorScale'

function CustomTooltip({ active, payload }) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        backgroundColor: 'rgba(255,255,255,0.95)',
        border: '1px solid #ccc',
        borderRadius: '4px',
        padding: '8px 12px'
      }}>
        <p style={{ margin: 0 }}>{payload[0].payload.fonds}</p>
        <p style={{ margin: '4px 0 0 0', fontWeight: 'bold' }}>
          {formatCurrency(payload[0].value)}
        </p>
      </div>
    )
  }
  return null
}

function FondsChart({ byFonds }) {
  const data = fondsToChartData(byFonds)

  return (
    <div className="chart-container">
      <h3>Répartition par fonds</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="fonds" />
          <YAxis />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Bar dataKey="montant_ue_total" name="Montant UE" fill={FONDS_COLORS.FEDER} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default FondsChart
