import { formatCurrency } from '../utils/colorScale'

function ObjectifsGrid({ objectifs, title = 'Objectifs Stratégiques' }) {
  if (!objectifs || Object.keys(objectifs).length === 0) {
    return <div className="py-8 text-center text-gray-500">Pas de données d'objectifs</div>
  }

  // Transformer en array et calculer totaux
  const items = Object.entries(objectifs).map(([name, data]) => ({
    name,
    montant: data.montant_ue_total || 0,
    count: data.count || 0,
  }))

  const totalMontant = items.reduce((sum, item) => sum + item.montant, 0)

  // Trier par montant décroissant
  items.sort((a, b) => b.montant - a.montant)

  // Assigner des couleurs alternées
  const colors = [
    'from-blue-500 to-blue-600',
    'from-cyan-500 to-cyan-600',
    'from-indigo-500 to-indigo-600',
    'from-violet-500 to-violet-600',
    'from-emerald-500 to-emerald-600',
    'from-teal-500 to-teal-600',
  ]

  return (
    <div className="w-full">
      <h3 className="text-2xl font-bold font-sans mb-6 text-gray-900 dark:text-white">{title}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((item, idx) => {
          const percent = totalMontant > 0 ? (item.montant / totalMontant * 100).toFixed(1) : 0
          const colorClass = colors[idx % colors.length]

          return (
            <div
              key={idx}
              className={`bg-gradient-to-br ${colorClass} text-white rounded-xl p-5 shadow-md hover:shadow-lg transition-all duration-200 transform hover:-translate-y-1`}
            >
              {/* Titre */}
              <h4 className="font-sans font-bold text-sm lg:text-base mb-3 line-clamp-2 leading-tight">
                {item.name}
              </h4>

              {/* Montant */}
              <div className="mb-3 pb-3 border-b border-white border-opacity-20">
                <p className="text-xs opacity-90 mb-1">Montant UE</p>
                <p className="text-lg lg:text-xl font-bold">{formatCurrency(item.montant)}</p>
              </div>

              {/* Count + % */}
              <div className="flex justify-between items-end">
                <div>
                  <p className="text-xs opacity-90">Projets</p>
                  <p className="text-lg font-bold">{item.count}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs opacity-90">Part</p>
                  <p className="text-lg font-bold">{percent}%</p>
                </div>
              </div>

              {/* Barre de progression */}
              <div className="mt-3 h-1.5 bg-white bg-opacity-20 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white bg-opacity-80 rounded-full transition-all duration-500"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ObjectifsGrid
