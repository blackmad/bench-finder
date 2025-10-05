import { divIcon, type LatLngBounds } from "leaflet"
import type React from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet"
import styled from "styled-components"
import "leaflet/dist/leaflet.css"
import "../../utils/leafletFix"
import type {
  BboxBenchResponse,
  ClusteredBenchData,
  ClusteredBenchListResponse,
} from "../../api"
import { useApp } from "../../contexts/AppContext"
import { benchApi } from "../../services/api"
import type { WebBenchData } from "../../api"
import LoadingSpinner from "../LoadingSpinner/LoadingSpinner"

const MapViewContainer = styled.div`
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  display: flex;
  background: #f0f0f0; /* Temporary debug background */
`

const MainMap = styled.div`
  flex: 1;
  height: 100%;
  min-height: 500px;
  position: relative;
  background: #e0e0e0; /* Temporary debug background */
`

const MapSidebar = styled.div`
  width: 400px;
  background: ${({ theme }) => theme.colors.background};
  border-left: 1px solid ${({ theme }) => theme.colors.border};
  display: flex;
  flex-direction: column;
  overflow: hidden;

  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    width: 100%;
    height: 40%;
    border-left: none;
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
`

const SidebarHeader = styled.div`
  padding: ${({ theme }) => theme.spacing[5]};
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  background: ${({ theme }) => theme.colors.backgroundTertiary};

  h3 {
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: ${({ theme }) => theme.typography.sizes.xl};
    font-weight: ${({ theme }) => theme.typography.weights.semibold};
  }
`

const SidebarStats = styled.div`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

const SidebarContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 0;
`

const SidebarPlaceholder = styled.div`
  padding: ${({ theme }) => theme.spacing[10]} ${({ theme }) => theme.spacing[5]};
  text-align: center;
  color: ${({ theme }) => theme.colors.textSecondary};

  .icon {
    font-size: ${({ theme }) => theme.typography.sizes["4xl"]};
    margin-bottom: ${({ theme }) => theme.spacing[4]};
    opacity: 0.7;
  }

  p {
    margin: 0 0 ${({ theme }) => theme.spacing[2]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.base};
  }

  small {
    color: ${({ theme }) => theme.colors.textTertiary};
    font-size: ${({ theme }) => theme.typography.sizes.sm};
  }
`

const SidebarLoading = styled.div`
  padding: ${({ theme }) => theme.spacing[8]};
  text-align: center;
  background: ${({ theme }) => theme.colors.backgroundTertiary};

  p {
    margin: ${({ theme }) => theme.spacing[4]} 0 0 0;
    color: ${({ theme }) => theme.colors.textSecondary};
  }
`

const MapBenchCard = styled.div<{ $selected?: boolean }>`
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderLight};
  padding: ${({ theme }) => theme.spacing[3]};
  cursor: pointer;
  transition: background-color ${({ theme }) => theme.transitions.fast};
  display: flex;
  gap: ${({ theme }) => theme.spacing[4]};
  background: ${({ $selected, theme }) =>
    $selected ? `${theme.colors.primary}10` : "transparent"};
  border-left: ${({ $selected, theme }) =>
    $selected ? `3px solid ${theme.colors.primary}` : "3px solid transparent"};

  &:hover {
    background: ${({ theme }) => theme.colors.backgroundTertiary};
  }
`

const MapCardImage = styled.div`
  width: 120px;
  height: 80px;
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  overflow: hidden;
  flex-shrink: 0;
  background: ${({ theme }) => theme.colors.gray100};

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: ${({ theme }) => theme.typography.sizes.xl};
    color: ${({ theme }) => theme.colors.gray400};
  }
`

const MapCardContent = styled.div`
  flex: 1;
  min-width: 0;
`

const MapCardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: ${({ theme }) => theme.spacing[2]};
`

const MapCardTitle = styled.div`
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
  line-height: ${({ theme }) => theme.typography.lineHeights.tight};
`

const MapCardConfidence = styled.div<{ $show: boolean }>`
  display: ${({ $show }) => ($show ? "block" : "none")};
  background: ${({ theme }) => theme.colors.success};
  color: white;
  padding: 2px ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.base};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.medium};
  white-space: nowrap;
`

const MapCardMeta = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing[3]};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-top: ${({ theme }) => theme.spacing[1]};

  span {
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing[1]};
  }
`

const SearchControls = styled.div`
  position: absolute;
  top: ${({ theme }) => theme.spacing[5]};
  right: ${({ theme }) => theme.spacing[5]};
  z-index: 1000;
  background: ${({ theme }) => theme.colors.background};
  padding: ${({ theme }) => theme.spacing[4]};
  border-radius: ${({ theme }) => theme.borderRadius.xl};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  max-width: 250px;

  @media (max-width: ${({ theme }) => theme.breakpoints.md}) {
    top: ${({ theme }) => theme.spacing[3]};
    right: ${({ theme }) => theme.spacing[3]};
    left: ${({ theme }) => theme.spacing[3]};
    max-width: none;
    padding: ${({ theme }) => theme.spacing[3]};
  }

  h4 {
    margin: 0 0 ${({ theme }) => theme.spacing[4]} 0;
    font-size: ${({ theme }) => theme.typography.sizes.base};
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  button {
    width: 100%;
    padding: ${({ theme }) => theme.spacing[2]} ${({ theme }) => theme.spacing[4]};
    border: none;
    border-radius: ${({ theme }) => theme.borderRadius.base};
    background: ${({ theme }) => theme.colors.primary};
    color: white;
    cursor: pointer;
    font-weight: ${({ theme }) => theme.typography.weights.medium};
    transition: background ${({ theme }) => theme.transitions.fast};

    &:hover {
      background: ${({ theme }) => theme.colors.primaryDark};
    }
  }
`

// Component to handle map events
const MapEventHandler: React.FC<{
  onBoundsChange: (bounds: LatLngBounds) => void
}> = ({ onBoundsChange }) => {
  const map = useMap()

  useEffect(() => {
    const handleMoveEnd = () => {
      const bounds = map.getBounds()
      onBoundsChange(bounds)
    }

    map.on("moveend", handleMoveEnd)

    // Trigger map resize after mount to ensure proper rendering
    setTimeout(() => {
      map.invalidateSize()
    }, 100)

    // Initial bounds
    setTimeout(() => {
      handleMoveEnd()
    }, 200)

    return () => {
      map.off("moveend", handleMoveEnd)
    }
  }, [map, onBoundsChange])

  return null
}

interface MapData {
  type: 'individual' | 'clustered'
  benches?: WebBenchData[]
  clusters?: ClusteredBenchData[]
  totalCount: number
  clusteringInfo?: Record<string, any>
}

const MapView: React.FC = () => {
  const { state } = useApp()
  const [mapData, setMapData] = useState<MapData>({
    type: "individual",
    benches: [],
    totalCount: 0,
  })
  const [selectedBenchId, setSelectedBenchId] = useState<number | null>(null)
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(
    null
  )
  const [loading, setLoading] = useState(false)
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const searchMapArea = useCallback(
    async (bounds?: LatLngBounds) => {
      if (!bounds) return

      setLoading(true)
      try {
        const params = {
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
          min_confidence: state.filters.minConfidence,
          limit: 200,
          sort_by: state.filters.sortBy,
          clustered: true, // Enable clustering by default
        }

        if (state.filters.sourceFilter !== "all") {
          ;(params as any).source = state.filters.sourceFilter
        }

        const response = await benchApi.getBenchesInBbox(params)

        // Handle both clustered and individual responses
        if ("clustered_benches" in response) {
          // Clustered response
          const clusteredResponse = response as ClusteredBenchListResponse
          setMapData({
            type: "clustered",
            clusters: clusteredResponse.clustered_benches,
            totalCount:
              clusteredResponse.pagination?.total_count ||
              clusteredResponse.clustered_benches.length,
            clusteringInfo: clusteredResponse.clustering_info,
          })
        } else {
          // Individual bench response
          const individualResponse = response as BboxBenchResponse
          setMapData({
            type: "individual",
            benches: individualResponse.benches as Bench[],
            totalCount:
              individualResponse.total_count ||
              individualResponse.benches.length,
          })
        }
      } catch (error) {
        console.error("Map search failed:", error)
        setMapData({ type: "individual", benches: [], totalCount: 0 })
      } finally {
        setLoading(false)
      }
    },
    [
      state.filters.minConfidence,
      state.filters.sortBy,
      state.filters.sourceFilter,
    ]
  )

  const handleBoundsChange = useCallback(
    async (bounds: LatLngBounds) => {
      // Clear previous timeout
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }

      // Debounce the search
      searchTimeoutRef.current = setTimeout(async () => {
        await searchMapArea(bounds)
      }, 500)
    },
    [searchMapArea]
  )

  const handleSearchHere = () => {
    // This would be triggered by the search button
    // For now, it's handled automatically by map movement
  }

  const handleBenchClick = useCallback((benchId: number) => {
    setSelectedBenchId(benchId)
    setSelectedClusterId(null)
  }, [])

  const handleClusterClick = useCallback((clusterId: number) => {
    setSelectedClusterId(clusterId)
    setSelectedBenchId(null)
  }, [])

  const defaultCenter: [number, number] = [
    state.filters.startLat,
    state.filters.startLng,
  ]

  return (
    <MapViewContainer>
      <MainMap>
        <MapContainer
          center={defaultCenter}
          zoom={13}
          style={{ height: "500px", width: "100%", minHeight: "500px" }}
          zoomControl={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          <MapEventHandler onBoundsChange={handleBoundsChange} />

          {/* Render clusters */}
          {mapData.type === "clustered" &&
            mapData.clusters?.map((clusterData) => (
              <Marker
                key={`cluster-${clusterData.cluster.cluster_id}`}
                position={[
                  clusterData.cluster.center_lat,
                  clusterData.cluster.center_lng,
                ]}
                icon={divIcon({
                  className: "custom-cluster-marker",
                  html: `<div style="
                  width: 32px;
                  height: 32px;
                  background: ${clusterData.cluster.cluster_id === selectedClusterId ? "#ef4444" : "#10b981"};
                  border: 3px solid white;
                  border-radius: 50%;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  color: white;
                  font-size: 11px;
                  font-weight: bold;
                  cursor: pointer;
                  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                ">${clusterData.cluster.bench_count}</div>`,
                  iconSize: [36, 36],
                  iconAnchor: [18, 18],
                })}
                eventHandlers={{
                  click: () =>
                    handleClusterClick(clusterData.cluster.cluster_id),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "250px" }}>
                    <h4>
                      Cluster of {clusterData.cluster.bench_count} Benches
                    </h4>
                    <p>
                      <strong>Average Confidence:</strong>{" "}
                      {(clusterData.cluster.avg_confidence * 100).toFixed(1)}%
                    </p>
                    <p>
                      <strong>Sources:</strong>{" "}
                      {clusterData.cluster.sources.join(", ")}
                    </p>
                    <p>
                      <strong>Distance:</strong>{" "}
                      {clusterData.distance_to_cluster_center < 1000
                        ? `${Math.round(clusterData.distance_to_cluster_center)}m`
                        : `${(clusterData.distance_to_cluster_center / 1000).toFixed(1)}km`}
                    </p>
                    <p>
                      <strong>Representative:</strong> Bench #
                      {clusterData.representative_bench.id}
                    </p>
                  </div>
                </Popup>
              </Marker>
            ))}

          {/* Render individual benches */}
          {mapData.type === "individual" &&
            mapData.benches?.map((bench) => (
              <Marker
                key={bench.id}
                position={[bench.lat, bench.lng]}
                icon={divIcon({
                  className: "custom-bench-marker",
                  html: `<div style="
                  width: 24px;
                  height: 24px;
                  background: ${bench.id === selectedBenchId ? "#ef4444" : "#3b82f6"};
                  border: 2px solid white;
                  border-radius: 50%;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  color: white;
                  font-size: 10px;
                  font-weight: bold;
                  cursor: pointer;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">🪑</div>`,
                  iconSize: [28, 28],
                  iconAnchor: [14, 14],
                })}
                eventHandlers={{
                  click: () => handleBenchClick(bench.id),
                }}
              >
                <Popup>
                  <div style={{ minWidth: "200px" }}>
                    <h4>Bench #{bench.id}</h4>
                    <p>
                      <strong>Confidence:</strong>{" "}
                      {(bench.best_confidence * 100).toFixed(1)}%
                    </p>
                    <p>
                      <strong>Distance:</strong>{" "}
                      {bench.distance_km < 1
                        ? `${bench.distance_meters}m`
                        : `${bench.distance_km}km`}
                    </p>
                    <p>
                      <strong>Images:</strong> {bench.image_count}
                    </p>
                  </div>
                </Popup>
              </Marker>
            ))}
        </MapContainer>

        <SearchControls>
          <h4>Search This Area</h4>
          <button onClick={handleSearchHere} type="button">
            🔍 Search Here
          </button>
        </SearchControls>
      </MainMap>

      <MapSidebar>
        <SidebarHeader>
          <h3>
            {mapData.type === "clustered"
              ? "Nearby Clusters"
              : "Nearby Benches"}
          </h3>
          <SidebarStats>
            {loading
              ? "Searching..."
              : mapData.type === "clustered"
                ? `${mapData.clusters?.length || 0} clusters (${mapData.totalCount} benches)`
                : `${mapData.benches?.length || 0} benches in view`}
            {mapData.clusteringInfo?.clustering_enabled && (
              <div
                style={{ fontSize: "0.75em", marginTop: "4px", opacity: 0.8 }}
              >
                📎 Clustering active (
                {mapData.clusteringInfo.clustering_distance_meters}m radius)
              </div>
            )}
          </SidebarStats>
        </SidebarHeader>

        <SidebarContent>
          {loading && (
            <SidebarLoading>
              <LoadingSpinner />
              <p>Searching for benches...</p>
            </SidebarLoading>
          )}

          {!loading && mapData.totalCount === 0 && (
            <SidebarPlaceholder>
              <div className="icon">🗺️</div>
              <p>No benches found in this area</p>
              <small>Try zooming out or adjusting your filters</small>
            </SidebarPlaceholder>
          )}

          {/* Render clustered data */}
          {!loading &&
            mapData.type === "clustered" &&
            mapData.clusters &&
            mapData.clusters.length > 0 && (
              <div>
                {mapData.clusters.map((clusterData) => {
                  const repBench = clusterData.representative_bench
                  const imageUrl = repBench.image_filenames?.[0]
                    ? `/images/${repBench.image_filenames[0]}`
                    : null

                  return (
                    <MapBenchCard
                      key={`cluster-${clusterData.cluster.cluster_id}`}
                      $selected={
                        selectedClusterId === clusterData.cluster.cluster_id
                      }
                      onClick={() =>
                        handleClusterClick(clusterData.cluster.cluster_id)
                      }
                    >
                      <MapCardImage>
                        {imageUrl ? (
                          <img
                            src={imageUrl}
                            alt={`Cluster ${clusterData.cluster.cluster_id}`}
                            loading="lazy"
                          />
                        ) : (
                          <div className="placeholder">📍</div>
                        )}
                      </MapCardImage>
                      <MapCardContent>
                        <MapCardHeader>
                          <MapCardTitle>
                            Cluster of {clusterData.cluster.bench_count} Benches
                          </MapCardTitle>
                          <MapCardConfidence $show={state.debugMode}>
                            {(clusterData.cluster.avg_confidence * 100).toFixed(
                              0
                            )}
                            %
                          </MapCardConfidence>
                        </MapCardHeader>
                        <MapCardMeta>
                          <span>
                            📍{" "}
                            {clusterData.distance_to_cluster_center < 1000
                              ? `${Math.round(clusterData.distance_to_cluster_center)}m`
                              : `${(clusterData.distance_to_cluster_center / 1000).toFixed(1)}km`}
                          </span>
                          <span>
                            🏷️ {clusterData.cluster.sources.join(", ")}
                          </span>
                        </MapCardMeta>
                      </MapCardContent>
                    </MapBenchCard>
                  )
                })}
              </div>
            )}

          {/* Render individual benches */}
          {!loading &&
            mapData.type === "individual" &&
            mapData.benches &&
            mapData.benches.length > 0 && (
              <div>
                {mapData.benches.map((bench) => {
                  const imageUrl = bench.image_filenames?.[0]
                    ? `/images/${bench.image_filenames[0]}`
                    : null

                  return (
                    <MapBenchCard
                      key={bench.id}
                      $selected={selectedBenchId === bench.id}
                      onClick={() => handleBenchClick(bench.id)}
                    >
                      <MapCardImage>
                        {imageUrl ? (
                          <img
                            src={imageUrl}
                            alt={`Bench ${bench.id}`}
                            loading="lazy"
                          />
                        ) : (
                          <div className="placeholder">🪑</div>
                        )}
                      </MapCardImage>
                      <MapCardContent>
                        <MapCardHeader>
                          <MapCardTitle>Bench #{bench.id}</MapCardTitle>
                          <MapCardConfidence $show={state.debugMode}>
                            {(bench.best_confidence * 100).toFixed(0)}%
                          </MapCardConfidence>
                        </MapCardHeader>
                        <MapCardMeta>
                          <span>
                            📍{" "}
                            {bench.distance_km < 1
                              ? `${bench.distance_meters}m`
                              : `${bench.distance_km}km`}
                          </span>
                        </MapCardMeta>
                      </MapCardContent>
                    </MapBenchCard>
                  )
                })}
              </div>
            )}
        </SidebarContent>
      </MapSidebar>
    </MapViewContainer>
  )
}

export default MapView
