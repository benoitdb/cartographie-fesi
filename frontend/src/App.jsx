import { useData } from './hooks/useData'
import { useRegion } from './context/RegionContext'
import NationalView from './pages/NationalView'
import RegionalView from './pages/RegionalView'
import './App.css'

function App() {
  const { selectedRegion, goToNational } = useRegion()
  const { data, loading, error } = useData()

  if (loading) return <div className="loading">Chargement des données...</div>
  if (error) return <div className="error">Erreur: {error}</div>
  if (!data) return <div className="error">Pas de données disponibles</div>

  return (
    <div className="app">
      <header className="app-header">
        <h1>📊 Cartographie des projets FESI</h1>
        <p>FEDER • FSE+ • FTJ</p>
      </header>

      <nav className="app-nav">
        <button
          className={!selectedRegion ? 'active' : ''}
          onClick={goToNational}
        >
          Vue Nationale
        </button>
        {selectedRegion && (
          <span className="region-badge">{selectedRegion}</span>
        )}
      </nav>

      <main className="app-main">
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
