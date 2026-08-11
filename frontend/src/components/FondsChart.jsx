import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { fondsToChartData, FONDS_COLORS } from '../utils/chartData'
import { formatCurrency } from '../utils/colorScale'

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.[0]) {
    const { fonds, montant_ue_total } = payload[0].payload
    return (
      <div style={{
        backgroundColor: 'rgba(255,255,255,0.95)',
        border: '1px solid #ccc',
        borderRadius: '4px',
        padding: '8px 12px'
      }}>
        <p style={{ margin: 0, fontWeight: '600' }}>{fonds}</p>
        <p style={{ margin: '4px 0 0 0', fontWeight: 'bold', color: '#1f8fb0' }}>
          {formatCurrency(montant_ue_total)}
        </p>
      </div>
    )
  }
  return null
}

function FondsChart({ byFonds }) {
  const data = fondsToChartData(byFonds)

  return (
    <div>
      <h3 className="text-xl font-bold font-sans mb-4 text-gray-900 dark:text-white">Répartition par fonds</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="fonds" />
          <YAxis />
          <Tooltip content={CustomTooltip} />
          <Legend />
          <Bar dataKey="montant_ue_total" name="Montant UE" fill={FONDS_COLORS.FEDER} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default FondsChart
