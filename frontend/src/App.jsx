import { useData } from './hooks/useData'
import { useRegion } from './context/RegionContext'
import NationalView from './pages/NationalView'
import RegionalView from './pages/RegionalView'

function App() {
  const { selectedRegion, goToNational } = useRegion()
  const { data, loading, error } = useData()

  if (loading) return <div className="py-8 text-center text-lg">Chargement des données...</div>
  if (error) return <div className="py-8 text-center text-lg text-red-600 dark:text-red-400">Erreur: {error}</div>
  if (!data) return <div className="py-8 text-center text-lg text-red-600 dark:text-red-400">Pas de données disponibles</div>

  return (
    <div className="flex flex-col min-h-screen bg-white dark:bg-gray-950">
      <header className="bg-primary text-white py-8 px-8 text-center shadow-lg">
        <h1 className="text-4xl font-bold mb-2">📊 Cartographie des projets FESI</h1>
        <p className="text-lg opacity-90">FEDER • FSE+ • FTJ</p>
      </header>

      <nav className="flex gap-4 px-8 py-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 items-center shadow-sm">
        <button
          onClick={goToNational}
          className={`px-4 py-2 rounded-lg font-medium transition-all ${
            !selectedRegion
              ? 'bg-primary text-white shadow-md'
              : 'bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-700'
          }`}
        >
          Vue Nationale
        </button>
        {selectedRegion && (
          <span className="ml-auto bg-secondary text-white px-4 py-2 rounded-full text-sm font-medium shadow-md">
            {selectedRegion}
          </span>
        )}
      </nav>

      <main className="flex-1 px-8 py-8 max-w-7xl mx-auto w-full">
        {selectedRegion ? (
          <RegionalView />
        ) : (
          <NationalView />
        )}
      </main>
    </div>
  )
}

export default App
