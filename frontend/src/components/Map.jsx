import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getColorScale, formatCurrency } from '../utils/colorScale'
import '../styles/components.css'

function MapContent({ geoJsonData, data, selectedRegion, onRegionSelect }) {
  const map = useMap()
  const byRegion = data?.aggregates?.by_region || {}
  const colorScale = getColorScale(byRegion)

  // Re-center map when selectedRegion changes
  useEffect(() => {
    if (!selectedRegion || !geoJsonData) return

    // Chercher la région dans le GeoJSON
    const feature = geoJsonData.features.find(f => f.properties.nom === selectedRegion)
    if (!feature) return

    const bounds = L.latLngBounds([])
    const { type, coordinates } = feature.geometry

    if (type === 'Polygon') {
      const coords = coordinates[0]
      coordinates[0].forEach(([lng, lat]) => bounds.extend([lat, lng]))
    } else if (type === 'MultiPolygon') {
      coordinates.forEach(polygon => {
        polygon[0].forEach(([lng, lat]) => bounds.extend([lat, lng]))
      })
    }

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }, [selectedRegion, geoJsonData, map])

  // Fonction pour styliser chaque région
  const getFeatureStyle = (feature) => {
    const regionName = feature.properties.nom
    const regionData = byRegion[regionName]
    const montant = regionData?.montant_ue_total || 0
    const color = colorScale(montant)

    return {
      fillColor: color,
      weight: selectedRegion === regionName ? 3 : 1,
      opacity: 1,
      color: selectedRegion === regionName ? '#ff6600' : '#666',
      dashArray: selectedRegion === regionName ? '5, 5' : '0',
      fillOpacity: 0.7
    }
  }

  // Callback pour chaque feature (région)
  const onEachFeature = (feature, layer) => {
    const regionName = feature.properties.nom
    const regionData = byRegion[regionName]

    // Créer le popup
    const popupContent = `
      <div class="geo-popup">
        <strong>${regionName}</strong>
        <br/>
        <span class="popup-stat">Projets: ${regionData?.count || 0}</span>
        <br/>
        <span class="popup-stat">Montant UE: ${formatCurrency(regionData?.montant_ue_total || 0)}</span>
      </div>
    `

    layer.bindPopup(popupContent)

    // Event: clic sur la région
    layer.on('click', () => {
      onRegionSelect(regionName)
    })

    // Hover effects
    layer.on('mouseover', () => {
      layer.setStyle({
        weight: 2,
        opacity: 1
      })
    })

    layer.on('mouseout', () => {
      if (selectedRegion !== regionName) {
        layer.setStyle({
          weight: 1
        })
      }
    })
  }

  return (
    <>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON data={geoJsonData} style={getFeatureStyle} onEachFeature={onEachFeature} />
    </>
  )
}

function Map({ data, selectedRegion, onRegionSelect }) {
  const [geoJsonData, setGeoJsonData] = useState(null)
  const [loading, setLoading] = useState(true)
  const byRegion = data?.aggregates?.by_region || {}

  // Charger le GeoJSON au montage
  useEffect(() => {
    fetch('/geo/regions-metropole.geojson')
      .then(res => res.json())
      .then(geoJson => {
        setGeoJsonData(geoJson)
        setLoading(false)
      })
      .catch(err => {
        console.error('Erreur chargement GeoJSON:', err)
        setLoading(false)
      })
  }, [])

  if (loading) return <div className="map-loading">Chargement de la carte...</div>
  if (!geoJsonData) return <div className="map-error">Impossible de charger la carte</div>

  return (
    <div className="map-wrapper">
      <MapContainer
        center={[46.2276, 2.2137]}
        zoom={6}
        scrollWheelZoom={false}
        style={{ height: '500px', width: '100%' }}
      >
        <MapContent geoJsonData={geoJsonData} data={data} selectedRegion={selectedRegion} onRegionSelect={onRegionSelect} />
      </MapContainer>

      {/* Légende */}
      <div className="map-legend">
        <div className="legend-title">Montants UE par région</div>
        <div className="legend-scale">
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#eff8fb' }}></div>
            <span>Faible</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#5cb8dc' }}></div>
            <span>Moyen</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#0d5a78' }}></div>
            <span>Élevé</span>
          </div>
        </div>
      </div>

      {/* Liste des régions pour DOM-TOM et accessibilité */}
      <div className="regions-list-below-map">
        <h4>Toutes les régions</h4>
        <div className="region-buttons-grid">
          {Object.keys(byRegion)
            .sort()
            .map((region) => (
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
