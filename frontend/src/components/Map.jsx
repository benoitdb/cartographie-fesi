import '../styles/components.css'

function Map({ data, selectedRegion, onRegionSelect }) {
  const regions = Object.keys(data.aggregates.by_region).sort()

  return (
    <div className="map-container">
      <h3>Carte interactive (Leaflet)</h3>
      <div className="map-placeholder">
        [Leaflet Choroplèthe - À implémenter]
      </div>

      <div className="regions-list">
        <h4>Régions ({regions.length})</h4>
        <div className="region-buttons">
          {regions.map((region) => (
            <button
              key={region}
              className={`region-btn ${selectedRegion === region ? 'selected' : ''}`}
              onClick={() => onRegionSelect(region)}
            >
              {region}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Map
