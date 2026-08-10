import React, { createContext, useContext, useState } from 'react'

const RegionContext = createContext()

export function RegionProvider({ children }) {
  const [selectedRegion, setSelectedRegion] = useState(null)

  const selectRegion = (region) => setSelectedRegion(region)
  const goToNational = () => setSelectedRegion(null)

  return (
    <RegionContext.Provider value={{ selectedRegion, selectRegion, goToNational }}>
      {children}
    </RegionContext.Provider>
  )
}

export function useRegion() {
  const context = useContext(RegionContext)
  if (!context) {
    throw new Error('useRegion must be used within RegionProvider')
  }
  return context
}
