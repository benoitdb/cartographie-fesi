import { formatCurrency } from '../utils/colorScale'

function KPIHeader({ aggregates }) {
  if (!aggregates) return null

  const stats = [
    {
      label: 'Montant UE Total',
      value: formatCurrency(aggregates.total_montant || 0),
      icon: '💶',
      color: 'from-blue-500 to-blue-600',
    },
    {
      label: 'Projets',
      value: (aggregates.total_count || 0).toLocaleString(),
      icon: '📋',
      color: 'from-cyan-500 to-cyan-600',
    },
    {
      label: 'Régions',
      value: Object.keys(aggregates.by_region || {}).length,
      icon: '🗺️',
      color: 'from-indigo-500 to-indigo-600',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {stats.map((stat, idx) => (
        <div
          key={idx}
          className={`bg-gradient-to-br ${stat.color} text-white rounded-xl p-6 shadow-lg`}
        >
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <p className="text-sm font-medium opacity-90 mb-2">{stat.label}</p>
              <p className="text-3xl font-bold font-sans">{stat.value}</p>
            </div>
            <span className="text-4xl">{stat.icon}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default KPIHeader
