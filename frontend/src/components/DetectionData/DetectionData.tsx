import React from 'react'
import styled from 'styled-components'
import { Target, Eye, Layers, Zap } from 'lucide-react'
import type { ApiDetectionItem } from '../../api'
import { DetectionSource } from '../../api'

const DetectionContainer = styled.div`
  background: linear-gradient(135deg, ${({ theme }) => theme.colors.gray50} 0%, ${({ theme }) => theme.colors.backgroundSecondary} 100%);
  border-radius: ${({ theme }) => theme.borderRadius.lg};
  padding: ${({ theme }) => theme.spacing[4]};
  margin-top: ${({ theme }) => theme.spacing[4]};
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
`

const DetectionHeader = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing[2]};
  margin-bottom: ${({ theme }) => theme.spacing[3]};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: ${({ theme }) => theme.typography.sizes.sm};
`

const DetectionItem = styled.div`
  background: ${({ theme }) => theme.colors.background};
  border: 1px solid ${({ theme }) => theme.colors.borderLight};
  border-radius: ${({ theme }) => theme.borderRadius.md};
  padding: ${({ theme }) => theme.spacing[3]};
  margin-bottom: ${({ theme }) => theme.spacing[2]};
  transition: all 0.2s ease-in-out;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  }

  &:last-child {
    margin-bottom: 0;
  }
`

const DetectionItemHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: ${({ theme }) => theme.spacing[2]};
`

const ConfidenceBadge = styled.span<{ $confidence: number }>`
  background: ${({ $confidence, theme }) => {
        if ($confidence >= 0.8) return theme.colors.success
        if ($confidence >= 0.6) return theme.colors.warning
        return theme.colors.error
    }};
  color: white;
  padding: ${({ theme }) => theme.spacing[1]} ${({ theme }) => theme.spacing[2]};
  border-radius: ${({ theme }) => theme.borderRadius.full};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  font-weight: ${({ theme }) => theme.typography.weights.semibold};
`

const DetectionDetails = styled.div`
  display: grid;
  gap: ${({ theme }) => theme.spacing[2]};
  font-size: ${({ theme }) => theme.typography.sizes.xs};
  color: ${({ theme }) => theme.colors.textSecondary};
`

const DetailRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`

const BoundingBoxInfo = styled.div`
  background: ${({ theme }) => theme.colors.primary}10;
  border: 1px solid ${({ theme }) => theme.colors.primary}30;
  border-radius: ${({ theme }) => theme.borderRadius.sm};
  padding: ${({ theme }) => theme.spacing[2]};
  margin-top: ${({ theme }) => theme.spacing[2]};
`

const PolygonInfo = styled.div`
  background: ${({ theme }) => theme.colors.success}10;
  border: 1px solid ${({ theme }) => theme.colors.success}30;
  border-radius: ${({ theme }) => theme.borderRadius.sm};
  padding: ${({ theme }) => theme.spacing[2]};
  margin-top: ${({ theme }) => theme.spacing[2]};
`

const NoDataMessage = styled.div`
  text-align: center;
  color: ${({ theme }) => theme.colors.textTertiary};
  font-style: italic;
  padding: ${({ theme }) => theme.spacing[4]};
`

interface DetectionDataProps {
    detectionItems: ApiDetectionItem[]
    detectionSource: DetectionSource
}

export const DetectionData: React.FC<DetectionDataProps> = ({
    detectionItems,
    detectionSource,
}) => {
    if (!detectionItems || detectionItems.length === 0) {
        return (
            <DetectionContainer>
                <DetectionHeader>
                    <Eye size={16} />
                    Detection Data
                </DetectionHeader>
                <NoDataMessage>No detection data available</NoDataMessage>
            </DetectionContainer>
        )
    }

    const getSourceIcon = (source: DetectionSource) => {
        switch (source) {
            case DetectionSource.ROBOFLOW:
                return <Target size={16} />
            case DetectionSource.ULTRALYTICS:
                return <Layers size={16} />
            case DetectionSource.MAPILLARY:
                return <Zap size={16} />
            default:
                return <Eye size={16} />
        }
    }

    const getSourceName = (source: DetectionSource) => {
        switch (source) {
            case DetectionSource.ROBOFLOW:
                return 'Roboflow'
            case DetectionSource.ULTRALYTICS:
                return 'Ultralytics'
            case DetectionSource.MAPILLARY:
                return 'Mapillary'
            case DetectionSource.MULTI_MODEL:
                return 'Multi-Model'
            case DetectionSource.NONE:
                return 'Unknown'
            default:
                return source
        }
    }

    return (
        <DetectionContainer>
            <DetectionHeader>
                {getSourceIcon(detectionSource)}
                Detection Data ({getSourceName(detectionSource)})
            </DetectionHeader>

            {detectionItems.map((item, index) => (
                <DetectionItem key={index}>
                    <DetectionItemHeader>
                        <span>
                            {item.class_name || 'Bench'} #{item.detection_id}
                        </span>
                        <ConfidenceBadge $confidence={item.confidence}>
                            {(item.confidence * 100).toFixed(1)}%
                        </ConfidenceBadge>
                    </DetectionItemHeader>

                    <DetectionDetails>
                        <DetailRow>
                            <span>Detection ID:</span>
                            <span>{item.detection_id}</span>
                        </DetailRow>
                        <DetailRow>
                            <span>Class:</span>
                            <span>{item.class_name || 'bench'}</span>
                        </DetailRow>
                        <DetailRow>
                            <span>Confidence:</span>
                            <span>{(item.confidence * 100).toFixed(2)}%</span>
                        </DetailRow>
                    </DetectionDetails>

                    {item.bbox && (
                        <BoundingBoxInfo>
                            <div style={{ fontWeight: 600, marginBottom: 4 }}>
                                📦 Bounding Box
                            </div>
                            <div style={{ fontSize: '11px', fontFamily: 'monospace' }}>
                                x: {item.bbox.x1.toFixed(1)}, y: {item.bbox.y1.toFixed(1)}
                                <br />
                                w: {(item.bbox.x2 - item.bbox.x1).toFixed(1)}, h: {(item.bbox.y2 - item.bbox.y1).toFixed(1)}
                            </div>
                        </BoundingBoxInfo>
                    )}

                    {item.polygon && (
                        <PolygonInfo>
                            <div style={{ fontWeight: 600, marginBottom: 4 }}>
                                🎯 Segmentation Polygon
                            </div>
                            <div style={{ fontSize: '11px', fontFamily: 'monospace' }}>
                                {item.polygon.coordinates.length} points
                            </div>
                        </PolygonInfo>
                    )}
                </DetectionItem>
            ))}
        </DetectionContainer>
    )
}

export default DetectionData
