import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { fondsToChartData, FONDS_COLORS } from '../utils/chartData'
import { formatCurrency } from '../utils/colorScale'

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
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
            formatter={(value, name) => {
              if (name === 'montant_ue_total') return formatCurrency(value)
              return value
            }}
            label={{ value: 'Montant UE', position: 'top' }}
          />
          <Legend />
          <Bar dataKey="montant_ue_total" name="Montant UE" fill={FONDS_COLORS.FEDER} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default FondsChart
