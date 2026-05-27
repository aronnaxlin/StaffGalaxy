import { useState, useCallback, useEffect } from 'react'
import { SigmaContainer, ControlsContainer, ZoomControl, FullScreenControl, useSigma } from '@react-sigma/core'
import '@react-sigma/core/lib/style.css'
import Graph from 'graphology'
import { GraphEvents } from './GraphEvents'
import { loadLevel, type Level } from '../data/loader'
import { swapGraph } from '../data/graphBuilder'

interface GalaxyViewProps {
  graph: Graph
  onNodeClick: (nodeId: string) => void
  navigateToNodeRef?: React.MutableRefObject<((nodeId: string) => void) | null>
  level: Level
  onLevelChange: (level: Level) => void
  selectedNode: string | null
}

const SIGMA_SETTINGS = {
  renderEdgeLabels: false,
  defaultEdgeType: 'line',
  labelFont: 'system-ui, sans-serif',
  labelSize: 11,
  labelColor: { color: '#94a3b8' },
  labelWeight: '400',
  labelRenderedSizeThreshold: 6,
  minCameraRatio: 0.045,
  maxCameraRatio: 2.2,
  zoomDuration: 140,
  zoomingRatio: 1.32,
  doubleClickZoomingRatio: 1.8,
  doubleClickZoomingDuration: 180,
  inertiaDuration: 120,
  inertiaRatio: 2.2,
  hideEdgesOnMove: true,
  hideLabelsOnMove: true,
  enableEdgeEvents: false,
  zIndex: true,
}

function CameraController({
  navigateToNodeRef,
  onLevelChange,
}: {
  navigateToNodeRef?: React.MutableRefObject<((nodeId: string) => void) | null>
  onLevelChange: (level: Level) => void
}) {
  const sigma = useSigma()

  useEffect(() => {
    sigma.getCamera().setState({ x: 0.5, y: 0.5, ratio: 1.05 })
  }, [sigma])

  useEffect(() => {
    if (!navigateToNodeRef) return
    navigateToNodeRef.current = async (nodeId: string) => {
      const graph = sigma.getGraph()
      if (!graph.hasNode(nodeId)) {
        const data = await loadLevel('l1')
        if (!data.nodes.some(node => node.id === nodeId)) return

        const camState = sigma.getCamera().getState()
        swapGraph(graph, data, 'l1')
        sigma.getCamera().setState(camState)
        sigma.refresh()
        onLevelChange('l1')
      }

      const display = sigma.getNodeDisplayData(nodeId)
      if (!display) return
      sigma.getCamera().animate({ x: display.x, y: display.y, ratio: 0.16 }, { duration: 420 })
    }
  }, [sigma, navigateToNodeRef, onLevelChange])

  return null
}

export function GalaxyView({
  graph,
  onNodeClick,
  navigateToNodeRef,
  level,
  onLevelChange,
  selectedNode,
}: GalaxyViewProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const handleNodeClick = useCallback(
    (nodeId: string) => onNodeClick(nodeId),
    [onNodeClick],
  )

  return (
    <SigmaContainer
      graph={graph}
      settings={SIGMA_SETTINGS}
      style={{ width: '100%', height: '100%', background: '#0a0a0f' }}
    >
      <CameraController navigateToNodeRef={navigateToNodeRef} onLevelChange={onLevelChange} />
      <GraphEvents
        onNodeClick={handleNodeClick}
        hoveredNode={hoveredNode}
        setHoveredNode={setHoveredNode}
        level={level}
        onLevelChange={onLevelChange}
        selectedNode={selectedNode}
      />
      <ControlsContainer position="bottom-right">
        <ZoomControl />
        <FullScreenControl />
      </ControlsContainer>
    </SigmaContainer>
  )
}
