function FiltersBar({ filters, onFiltersChange }) {
  const FONDS = ['FEDER', 'FSE+', 'FTJ']

  const handleFondsToggle = (fond) => {
    const newFonds = filters.fonds.includes(fond)
      ? filters.fonds.filter(f => f !== fond)
      : [...filters.fonds, fond]
    onFiltersChange({ ...filters, fonds: newFonds })
  }

  const handleMontantChange = (e) => {
    onFiltersChange({ ...filters, montantMin: parseFloat(e.target.value) || 0 })
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-md p-6">
      <h3 className="text-lg font-bold font-sans mb-4 text-gray-900 dark:text-white">Filtrer les données</h3>

      {/* Filtres Fonds */}
      <div className="mb-6">
        <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 block mb-3">Fonds</label>
        <div className="space-y-2">
          {FONDS.map(fond => (
            <label key={fond} className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.fonds.includes(fond)}
                onChange={() => handleFondsToggle(fond)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">{fond}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Filtres Montant */}
      <div className="mb-6">
        <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 block mb-3">
          Montant minimum (M€)
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="0"
            max="500"
            step="10"
            value={filters.montantMin}
            onChange={handleMontantChange}
            className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-12 text-right">
            {filters.montantMin}M€
          </span>
        </div>
      </div>

      {/* Reset */}
      <button
        onClick={() => onFiltersChange({ fonds: ['FEDER', 'FSE+', 'FTJ'], montantMin: 0 })}
        className="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
      >
        Réinitialiser filtres
      </button>
    </div>
  )
}

export default FiltersBar
