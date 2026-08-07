import { useState, useEffect } from 'react'

export function useData() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await fetch('/data.json')
        if (!response.ok) throw new Error('Impossible de charger les données')
        const jsonData = await response.json()
        setData(jsonData)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const getOperationsByRegion = (region) => {
    if (!data) return []
    return data.operations.filter(op => op['Région de l' + 'opération'] === region)
  }

  const getAggregatesByRegion = (region) => {
    if (!data) return null
    return data.aggregates.by_region[region]
  }

  return {
    data,
    loading,
    error,
    getOperationsByRegion,
    getAggregatesByRegion,
  }
}
