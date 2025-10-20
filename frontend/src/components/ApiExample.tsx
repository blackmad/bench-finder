import { useQuery } from "@tanstack/react-query"
import type React from "react"
import { useEffect, useState } from "react"
import styled from "styled-components"
import type { BenchListResponse, ClusteredBenchListResponse, WebBenchData } from "../api"
import { benchApi, checkApiHealth } from "../services/benchApi"

// Example component demonstrating the new OpenAPI-generated client
const ApiExample: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<Record<
    string,
    string
  > | null>(null)

  // Example 1: Health check using regular fetch
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await checkApiHealth()
        setHealthStatus(health)
      } catch (error) {
        console.error("Health check failed:", error)
        setHealthStatus({ status: "unhealthy", error: String(error) })
      }
    }

    checkHealth()
  }, [])

  // Example 2: Using React Query with the generated client
  const {
    data: benchesData,
    isLoading,
    error,
    refetch,
  } = useQuery<BenchListResponse | ClusteredBenchListResponse>({
    queryKey: ["benches", { page: 0, minConfidence: 0.8 }],
    queryFn: () =>
      benchApi.getBenches({
        page: 0,
        pageSize: 5,
        minConfidence: 0.8,
        sortBy: "confidence",
        clustered: false, // We want individual benches for the example
      }),
    staleTime: 1000 * 60 * 5, // 5 minutes
  })

  // Example 3: Get random bench
  const [randomBench, setRandomBench] = useState<WebBenchData | null>(null)
  const [isLoadingRandom, setIsLoadingRandom] = useState(false)

  const getRandomBench = async () => {
    setIsLoadingRandom(true)
    try {
      const result = await benchApi.getRandomBench({
        minConfidence: 0.9,
        source: null,
      })
      setRandomBench(result.bench)
    } catch (error) {
      console.error("Failed to get random bench:", error)
    } finally {
      setIsLoadingRandom(false)
    }
  }

  return (
    <Container>
      <Title>🚀 FastAPI + OpenAPI Integration Demo</Title>

      {/* Health Status */}
      <Section>
        <SectionTitle>📊 API Health Status</SectionTitle>
        {healthStatus ? (
          <HealthStatus healthy={healthStatus.status === "healthy"}>
            <strong>Status:</strong> {healthStatus.status}
            <br />
            <strong>Database:</strong> {healthStatus.database || "unknown"}
            <br />
            <strong>Mapillary:</strong> {healthStatus.mapillary || "unknown"}
          </HealthStatus>
        ) : (
          <Loading>Checking API health...</Loading>
        )}
      </Section>

      {/* Bench List */}
      <Section>
        <SectionTitle>🪑 High Confidence Benches</SectionTitle>
        {isLoading && <Loading>Loading benches...</Loading>}
        {error && (
          <ErrorBox>
            <strong>Error:</strong> {error.message}
            <RefreshButton onClick={() => refetch()}>Retry</RefreshButton>
          </ErrorBox>
        )}
        {benchesData && (
          <>
            {"benches" in benchesData && (
              <>
                <Stats>
                  Found <strong>{benchesData.pagination.total_count}</strong>{" "}
                  benches (showing {benchesData.benches.length})
                </Stats>
                <BenchList>
                  {benchesData.benches.map((bench: WebBenchData) => (
                <BenchCard key={bench.id}>
                  <BenchHeader>
                    <BenchId>Bench #{bench.id}</BenchId>
                    <ConfidenceBadge confidence={bench.best_confidence}>
                      {(bench.best_confidence * 100).toFixed(1)}%
                    </ConfidenceBadge>
                  </BenchHeader>
                  <BenchDetails>
                    <DetailItem>
                      <strong>Location:</strong> {bench.lat.toFixed(4)},{" "}
                      {bench.lng.toFixed(4)}
                    </DetailItem>
                    <DetailItem>
                      <strong>Source:</strong> {bench.source}
                    </DetailItem>
                    <DetailItem>
                      <strong>Detection:</strong> {bench.detection_type}
                    </DetailItem>
                    <DetailItem>
                      <strong>Images:</strong> {bench.image_count}
                      {bench.has_segmentation && " 🎯"}
                    </DetailItem>
                    <DetailItem>
                      <strong>Distance:</strong> {bench.distance_km.toFixed(2)}{" "}
                      km
                    </DetailItem>
                  </BenchDetails>
                  <ConfidenceDetails>
                    {(bench.roboflow_confidence || 0) > 0 && (
                      <span>
                        RF: {((bench.roboflow_confidence || 0) * 100).toFixed(1)}%
                      </span>
                    )}
                    {(bench.ultralytics_confidence || 0) > 0 && (
                      <span>
                        UL: {((bench.ultralytics_confidence || 0) * 100).toFixed(1)}%
                      </span>
                    )}
                    {(bench.mapillary_confidence || 0) > 0 && (
                      <span>
                        MP: {((bench.mapillary_confidence || 0) * 100).toFixed(1)}%
                      </span>
                    )}
                  </ConfidenceDetails>
                </BenchCard>
              ))}
                </BenchList>
              </>
            )}
          </>
        )}
      </Section>

      {/* Random Bench */}
      <Section>
        <SectionTitle>🎲 Random Bench Discovery</SectionTitle>
        <RandomButton onClick={getRandomBench} disabled={isLoadingRandom}>
          {isLoadingRandom ? "Finding Random Bench..." : "Get Random Bench"}
        </RandomButton>
        {randomBench && (
          <RandomBenchCard>
            <h4>🎯 Random Bench #{randomBench.id}</h4>
            <p>
              <strong>Confidence:</strong>{" "}
              {(randomBench.best_confidence * 100).toFixed(1)}%
            </p>
            <p>
              <strong>Location:</strong> {randomBench.lat.toFixed(4)},{" "}
              {randomBench.lng.toFixed(4)}
            </p>
            <p>
              <strong>Source:</strong> {randomBench.source}
            </p>
            {randomBench.tags && Object.keys(randomBench.tags).length > 0 && (
              <div>
                <strong>Tags:</strong>
                <TagList>
                  {Object.entries(randomBench.tags).map(([key, value]) => (
                    <Tag key={key}>
                      {key}: {String(value)}
                    </Tag>
                  ))}
                </TagList>
              </div>
            )}
          </RandomBenchCard>
        )}
      </Section>

      {/* TypeScript Info */}
      <Section>
        <SectionTitle>💡 TypeScript Integration</SectionTitle>
        <InfoBox>
          <p>This component demonstrates:</p>
          <ul>
            <li>
              ✅ <strong>Type-safe API calls</strong> - All parameters and
              responses are typed
            </li>
            <li>
              ✅ <strong>Auto-completion</strong> - IDE provides IntelliSense
              for all API methods
            </li>
            <li>
              ✅ <strong>Compile-time validation</strong> - TypeScript catches
              API mismatches
            </li>
            <li>
              ✅ <strong>Generated documentation</strong> - All types include
              OpenAPI descriptions
            </li>
            <li>
              ✅ <strong>React Query integration</strong> - Seamless caching and
              state management
            </li>
          </ul>
          <CodeExample>
            {`// Type-safe API call with full IntelliSense
const response: BenchListResponse = await benchApi.getBenches({
  page: 0,
  minConfidence: 0.8,  // ✅ Validated (0.0 - 1.0)
  sortBy: 'confidence' // ✅ Enum: distance | confidence | images | recent
})`}
          </CodeExample>
        </InfoBox>
      </Section>
    </Container>
  )
}

export default ApiExample

// Styled Components
const Container = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  font-family: system-ui, -apple-system, sans-serif;
`

const Title = styled.h1`
  font-size: 2rem;
  margin-bottom: 2rem;
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`

const Section = styled.div`
  margin-bottom: 3rem;
  padding: 1.5rem;
  border: 1px solid #e1e5e9;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
`

const SectionTitle = styled.h2`
  font-size: 1.25rem;
  margin-bottom: 1rem;
  color: #2d3748;
`

const HealthStatus = styled.div<{ healthy: boolean }>`
  padding: 1rem;
  border-radius: 4px;
  background: ${(props) => (props.healthy ? "#f0fff4" : "#fed7d7")};
  color: ${(props) => (props.healthy ? "#22543d" : "#742a2a")};
  border: 1px solid ${(props) => (props.healthy ? "#9ae6b4" : "#feb2b2")};
`

const Loading = styled.div`
  padding: 1rem;
  text-align: center;
  color: #4a5568;
  font-style: italic;
`

const ErrorBox = styled.div`
  padding: 1rem;
  background: #fed7d7;
  color: #742a2a;
  border-radius: 4px;
  border: 1px solid #feb2b2;
  display: flex;
  justify-content: space-between;
  align-items: center;
`

const RefreshButton = styled.button`
  background: #e53e3e;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;

  &:hover {
    background: #c53030;
  }
`

const Stats = styled.p`
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: #4a5568;
`

const BenchList = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
`

const BenchCard = styled.div`
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 1rem;
  background: #f8fafc;
`

const BenchHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
`

const BenchId = styled.h4`
  margin: 0;
  color: #2d3748;
`

const ConfidenceBadge = styled.span<{ confidence: number }>`
  background: ${(props) => (props.confidence > 0.9 ? "#48bb78" : props.confidence > 0.8 ? "#ed8936" : "#e53e3e")};
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
`

const BenchDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.5rem;
`

const DetailItem = styled.div`
  font-size: 0.85rem;
  color: #4a5568;
`

const ConfidenceDetails = styled.div`
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #718096;

  span {
    background: #edf2f7;
    padding: 0.125rem 0.25rem;
    border-radius: 4px;
  }
`

const RandomButton = styled.button`
  background: #4299e1;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  margin-bottom: 1rem;

  &:hover:not(:disabled) {
    background: #3182ce;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`

const RandomBenchCard = styled.div`
  background: #e6fffa;
  border: 1px solid #81e6d9;
  border-radius: 8px;
  padding: 1rem;

  h4 {
    margin: 0 0 0.5rem 0;
    color: #234e52;
  }

  p {
    margin: 0.25rem 0;
    color: #2d3748;
    font-size: 0.9rem;
  }
`

const TagList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.5rem;
`

const Tag = styled.span`
  background: #bee3f8;
  color: #2b6cb0;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-size: 0.75rem;
`

const InfoBox = styled.div`
  background: #f7fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 1.5rem;

  ul {
    margin: 1rem 0;
    padding-left: 1.5rem;
  }

  li {
    margin: 0.5rem 0;
    color: #4a5568;
  }
`

const CodeExample = styled.pre`
  background: #1a202c;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85rem;
  margin-top: 1rem;

  // Syntax highlighting
  .keyword { color: #f56565; }
  .string { color: #68d391; }
  .comment { color: #a0aec0; }
`
