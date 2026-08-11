import { formatCurrency } from '../utils/colorScale'

function StatsGrid({ aggregates }) {
  const regionStats = Object.values(aggregates.by_region || {})[0]

  if (!regionStats) return <div className="py-4 text-gray-500">Pas de données</div>

  const stats = [
    { label: 'Projets', value: regionStats.count, icon: '📋' },
    { label: 'Montant UE Total', value: formatCurrency(regionStats.montant_ue_total), icon: '💶' },
    { label: 'Montant UE Moyen', value: formatCurrency(regionStats.montant_ue_moyen), icon: '📊' },
    { label: 'Dépenses Total', value: formatCurrency(regionStats.depenses_total), icon: '💰' },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
      {stats.map((stat, idx) => (
        <div
          key={idx}
          className="bg-gradient-to-br from-blue-500 via-blue-600 to-blue-700 text-white rounded-xl p-5 shadow-md hover:shadow-lg transition-shadow duration-200"
        >
          <div className="flex justify-between items-start gap-3">
            <div className="flex-1">
              <p className="text-sm font-medium opacity-90 mb-2">{stat.label}</p>
              <p className="text-xl lg:text-2xl font-bold font-sans break-words">{stat.value}</p>
            </div>
            <span className="text-2xl flex-shrink-0">{stat.icon}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default StatsGrid
