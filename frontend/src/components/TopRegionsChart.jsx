import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { regionsToChartData } from '../utils/chartData'
import { formatCurrency } from '../utils/colorScale'

function TopRegionsChart({ byRegion }) {
  const data = regionsToChartData(byRegion)

  return (
    <div>
      <h3 className="text-xl font-bold font-sans mb-4 text-gray-900 dark:text-white">Montants UE par région</h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} layout="vertical" margin={{ left: 150, right: 30 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis dataKey="region" type="category" width={140} tick={{ fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255,255,255,0.95)',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
            formatter={(value) => formatCurrency(value)}
          />
          <Bar dataKey="montant_ue_total" fill="#1f8fb0" name="Montant UE" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default TopRegionsChart
