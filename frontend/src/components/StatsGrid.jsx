import '../styles/components.css'

function StatsGrid({ aggregates }) {
  const regionStats = Object.values(aggregates.by_region || {})[0]

  if (!regionStats) return <div>Pas de données</div>

  const formatCurrency = (value) => {
    if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B€'
    if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M€'
    if (value >= 1e3) return (value / 1e3).toFixed(1) + 'k€'
    return value.toFixed(0) + '€'
  }

  return (
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-label">Projets</div>
        <div className="stat-value">{regionStats.count}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Montant UE Total</div>
        <div className="stat-value">{formatCurrency(regionStats.montant_ue_total)}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Montant UE Moyen</div>
        <div className="stat-value">{formatCurrency(regionStats.montant_ue_moyen)}</div>
      </div>

      <div className="stat-card">
        <div className="stat-label">Dépenses Total</div>
        <div className="stat-value">{formatCurrency(regionStats.depenses_total)}</div>
      </div>
    </div>
  )
}

export default StatsGrid
