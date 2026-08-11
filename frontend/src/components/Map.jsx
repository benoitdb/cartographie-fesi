import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getColorScale, formatCurrency } from '../utils/colorScale'

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
  if (!geoJsonData) return <div className="py-4 text-center text-red-600 dark:text-red-400">Impossible de charger la carte</div>

  return (
    <div className="flex flex-col h-full">
      <MapContainer
        center={[46.2276, 2.2137]}
        zoom={6}
        scrollWheelZoom={false}
        style={{ height: '500px', width: '100%' }}
      >
        <MapContent geoJsonData={geoJsonData} data={data} selectedRegion={selectedRegion} onRegionSelect={onRegionSelect} />
      </MapContainer>

      {/* Légende */}
      <div className="absolute top-5 right-5 bg-white dark:bg-gray-900 rounded-lg p-4 shadow-lg z-400 max-w-xs">
        <h4 className="font-sans font-semibold text-gray-900 dark:text-white mb-3 text-sm">Montants UE par région</h4>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded border border-gray-300" style={{ backgroundColor: '#eff8fb' }}></div>
            <span className="text-sm text-gray-700 dark:text-gray-300">Faible</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded border border-gray-300" style={{ backgroundColor: '#5cb8dc' }}></div>
            <span className="text-sm text-gray-700 dark:text-gray-300">Moyen</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded border border-gray-300" style={{ backgroundColor: '#0d5a78' }}></div>
            <span className="text-sm text-gray-700 dark:text-gray-300">Élevé</span>
          </div>
        </div>
      </div>

      {/* Liste des régions pour DOM-TOM et accessibilité */}
      <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-800">
        <h4 className="font-sans font-semibold text-gray-900 dark:text-white mb-3 text-sm">Toutes les régions</h4>
        <div className="flex flex-wrap gap-2">
          {Object.keys(byRegion)
            .sort()
            .map((region) => (
              <button
                key={region}
                onClick={() => onRegionSelect(region)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  selectedRegion === region
                    ? 'bg-primary text-white shadow-md'
                    : 'bg-gray-200 dark:bg-gray-800 text-gray-900 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-700'
                }`}
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
