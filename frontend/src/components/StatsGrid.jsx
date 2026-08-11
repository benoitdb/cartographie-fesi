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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, idx) => (
        <div
          key={idx}
          className="bg-gradient-to-br from-primary to-blue-600 dark:from-blue-700 dark:to-blue-900 text-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow"
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-sm font-medium opacity-90 mb-1">{stat.label}</div>
              <div className="text-2xl font-bold font-sans">{stat.value}</div>
            </div>
            <span className="text-2xl">{stat.icon}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default StatsGrid
