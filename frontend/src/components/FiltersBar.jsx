function FiltersBar({ filters, onFiltersChange }) {
  const FONDS = ['FEDER', 'FSE+', 'FTJ']

  const handleFondsToggle = (fond) => {
    const newFonds = filters.fonds.includes(fond)
      ? filters.fonds.filter(f => f !== fond)
      : [...filters.fonds, fond]
    onFiltersChange({ ...filters, fonds: newFonds })
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

      {/* Reset */}
      <button
        onClick={() => onFiltersChange({ fonds: ['FEDER', 'FSE+', 'FTJ'] })}
        className="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
      >
        Réinitialiser filtres
      </button>
    </div>
  )
}

export default FiltersBar
