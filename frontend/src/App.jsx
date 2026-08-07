import { useState } from 'react'
import { useData } from './hooks/useData'
import NationalView from './pages/NationalView'
import RegionalView from './pages/RegionalView'
import './App.css'

function App() {
  const [selectedRegion, setSelectedRegion] = useState(null)
  const { data, loading, error } = useData()

  if (loading) return <div className="loading">Chargement des données...</div>
  if (error) return <div className="error">Erreur: {error}</div>
  if (!data) return <div className="error">Pas de données disponibles</div>

  const handleRegionSelect = (region) => {
    setSelectedRegion(region)
  }

  const handleBackToNational = () => {
    setSelectedRegion(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>📊 Cartographie des projets FESI</h1>
        <p>FEDER • FSE+ • FTJ</p>
      </header>

      <nav className="app-nav">
        <button
          className={!selectedRegion ? 'active' : ''}
          onClick={handleBackToNational}
        >
          Vue Nationale
        </button>
        {selectedRegion && (
          <span className="region-badge">{selectedRegion}</span>
        )}
      </nav>

      <main className="app-main">
        {selectedRegion ? (
          <RegionalView region={selectedRegion} onBack={handleBackToNational} />
        ) : (
          <NationalView onRegionSelect={handleRegionSelect} />
        )}
      </main>
    </div>
  )
}

export default App
