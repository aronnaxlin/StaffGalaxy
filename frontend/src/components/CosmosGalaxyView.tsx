import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Graph as CosmosGraph } from '@cosmos.gl/graph'
import Graph from 'graphology'
import { loadLevel, type Level } from '../data/loader'
import { swapGraph } from '../data/graphBuilder'

interface CosmosGalaxyViewProps {
  graph: Graph
  onNodeClick: (nodeId: string) => void
  navigateToNodeRef?: React.MutableRefObject<((nodeId: string) => void) | null>
  level: Level
  onLevelChange: (level: Level) => void
  selectedNode: string | null
}

interface CosmosPayload {
  nodeIds: string[]
  positions: Float32Array
  pointColors: Float32Array
  pointSizes: Float32Array
  edgeRecords: EdgeRecord[]
}

interface EdgeRecord {
  sourceIndex: number
  targetIndex: number
  sharedWorksCount: number
}

const SEARCH_ZOOM_SCALE = 3.8
const DEFAULT_FOCUS_NODE_ID = '94'
const COSMOS_SPACE_SIZE = 8192
const COSMOS_LAYOUT_SIZE = 4300

function readRgb(value: unknown): [number, number, number] {
  if (typeof value !== 'string') return [212, 215, 223]
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!match) return [212, 215, 223]
  return [Number(match[1]), Number(match[2]), Number(match[3])]
}

function minSharedForZoom(level: Level, zoom: number): number {
  if (level === 'person') return 1

  if (level === 'global') {
    if (zoom > 0.9) return 40
    if (zoom > 0.65) return 24
    return 12
  }

  if (zoom > 0.8) return 24
  if (zoom > 0.55) return 16
  return 12
}

function buildEdgeArrays(edgeRecords: EdgeRecord[], minShared: number, level: Level) {
  const visibleEdges = edgeRecords.filter(edge => edge.sharedWorksCount >= minShared)
  const links = new Float32Array(visibleEdges.length * 2)
  const linkColors = new Float32Array(visibleEdges.length * 4)
  const linkWidths = new Float32Array(visibleEdges.length)

  visibleEdges.forEach((edge, index) => {
    links[index * 2] = edge.sourceIndex
    links[index * 2 + 1] = edge.targetIndex

    const t = Math.min(1, Math.log10(1 + edge.sharedWorksCount) / 2)
    linkColors[index * 4] = 148
    linkColors[index * 4 + 1] = 163
    linkColors[index * 4 + 2] = 184
    linkColors[index * 4 + 3] = level === 'person' ? 42 + t * 42 : 14 + t * 26
    linkWidths[index] = level === 'person' ? 0.16 + t * 0.42 : 0.08 + t * 0.28
  })

  return { links, linkColors, linkWidths, visibleEdgeCount: visibleEdges.length }
}

function buildCosmosPayload(graph: Graph): CosmosPayload {
  const nodeIds = graph.nodes()
  const indexById = new Map(nodeIds.map((id, index) => [id, index]))
  const positions = new Float32Array(nodeIds.length * 2)
  const rawPositions = new Float32Array(nodeIds.length * 2)
  const pointColors = new Float32Array(nodeIds.length * 4)
  const pointSizes = new Float32Array(nodeIds.length)

  nodeIds.forEach((nodeId, index) => {
    const attrs = graph.getNodeAttributes(nodeId)
    rawPositions[index * 2] = Number(attrs.x ?? 0)
    rawPositions[index * 2 + 1] = Number(attrs.y ?? 0)

    const [r, g, b] = readRgb(attrs.color)
    pointColors[index * 4] = r
    pointColors[index * 4 + 1] = g
    pointColors[index * 4 + 2] = b
    pointColors[index * 4 + 3] = 255
    pointSizes[index] = attrs.isCenter
      ? 14
      : Math.max(3.2, Number(attrs.size ?? 3) * (graph.order <= 700 ? 1.35 : 1.15))
  })

  const xs = nodeIds.map((_id, index) => rawPositions[index * 2])
  const ys = nodeIds.map((_id, index) => rawPositions[index * 2 + 1])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const span = Math.max(maxX - minX, maxY - minY, 1)
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2

  nodeIds.forEach((_nodeId, index) => {
    positions[index * 2] = COSMOS_SPACE_SIZE / 2 + ((rawPositions[index * 2] - centerX) / span) * COSMOS_LAYOUT_SIZE
    positions[index * 2 + 1] = COSMOS_SPACE_SIZE / 2 + ((rawPositions[index * 2 + 1] - centerY) / span) * COSMOS_LAYOUT_SIZE
  })

  const edgeRecords = graph.edges().map(edge => {
    const [source, target] = graph.extremities(edge)
    const sharedWorksCount = Number(graph.getEdgeAttribute(edge, 'sharedWorksCount') ?? 0)
    return {
      sourceIndex: indexById.get(source) ?? 0,
      targetIndex: indexById.get(target) ?? 0,
      sharedWorksCount,
    }
  })

  return { nodeIds, positions, pointColors, pointSizes, edgeRecords }
}

export function CosmosGalaxyView({
  graph,
  onNodeClick,
  navigateToNodeRef,
  level,
  onLevelChange,
  selectedNode,
}: CosmosGalaxyViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cosmosRef = useRef<CosmosGraph | null>(null)
  const payloadRef = useRef<CosmosPayload | null>(null)
  const selectedNodeRef = useRef<string | null>(selectedNode)
  const edgeCutoffRef = useRef(minSharedForZoom(level, 1))
  const applyEdgeDensityRef = useRef<(() => void) | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [visibleEdgeCount, setVisibleEdgeCount] = useState(0)
  const [edgeCutoff, setEdgeCutoff] = useState(() => minSharedForZoom(level, 1))
  const payload = useMemo(() => {
    void level
    return buildCosmosPayload(graph)
  }, [graph, level])

  const focusNode = useCallback((nodeId: string, animate = true) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return false

    const index = payload.nodeIds.indexOf(nodeId)
    if (index < 0) return false

    cosmos.selectPointByIndex(index, true)
    cosmos.setConfig({ focusedPointIndex: index })
    if (animate) cosmos.zoomToPointByIndex(index, 420, SEARCH_ZOOM_SCALE, false)
    return true
  }, [])

  const applyEdgeDensity = useCallback((force = false) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return

    const nextCutoff = minSharedForZoom(level, cosmos.getZoomLevel())
    if (!force && edgeCutoffRef.current === nextCutoff) return

    const arrays = buildEdgeArrays(payload.edgeRecords, nextCutoff, level)
    cosmos.setLinks(arrays.links)
    cosmos.setLinkColors(arrays.linkColors)
    cosmos.setLinkWidths(arrays.linkWidths)
    cosmos.render()

    edgeCutoffRef.current = nextCutoff
    setEdgeCutoff(nextCutoff)
    setVisibleEdgeCount(arrays.visibleEdgeCount)
  }, [level])

  useEffect(() => {
    applyEdgeDensityRef.current = () => applyEdgeDensity()
  }, [applyEdgeDensity])

  useEffect(() => {
    selectedNodeRef.current = selectedNode
    if (!selectedNode) {
      cosmosRef.current?.unselectPoints()
      cosmosRef.current?.setConfig({ focusedPointIndex: undefined })
      return
    }
    focusNode(selectedNode, false)
  }, [focusNode, selectedNode])

  useEffect(() => {
    payloadRef.current = payload
  }, [payload])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const cosmos = new CosmosGraph(container, {
      backgroundColor: '#0a0a0f',
      enableSimulation: false,
      spaceSize: COSMOS_SPACE_SIZE,
      rescalePositions: false,
      fitViewOnInit: true,
      fitViewDelay: 80,
      fitViewDuration: 320,
      fitViewPadding: 0.18,
      hoveredPointCursor: 'pointer',
      renderHoveredPointRing: true,
      hoveredPointRingColor: '#e5e7eb',
      focusedPointRingColor: '#fef08a',
      pointDefaultColor: '#d4d7df',
      pointGreyoutOpacity: 0.08,
      pointOpacity: 0.96,
      pointSizeScale: 1.08,
      linkDefaultColor: [148, 163, 184, 0.1],
      linkGreyoutOpacity: 0.04,
      linkOpacity: 1,
      linkVisibilityDistanceRange: [35, 180],
      linkVisibilityMinTransparency: 0.02,
      scalePointsOnZoom: true,
      scaleLinksOnZoom: false,
      pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      attribution: '',
      onPointClick: (index) => {
        const nodeId = payloadRef.current?.nodeIds[index]
        if (!nodeId) return
        selectedNodeRef.current = nodeId
        onNodeClick(nodeId)
        focusNode(nodeId, false)
      },
      onBackgroundClick: () => {
        cosmos.unselectPoints()
        cosmos.setConfig({ focusedPointIndex: undefined })
      },
      onPointMouseOver: (index) => {
        setHoveredNode(payloadRef.current?.nodeIds[index] ?? null)
      },
      onPointMouseOut: () => {
        setHoveredNode(null)
      },
      onZoomEnd: () => {
        applyEdgeDensityRef.current?.()
      },
    })

    cosmosRef.current = cosmos
    return () => {
      cosmos.destroy()
      cosmosRef.current = null
    }
  }, [focusNode, onNodeClick])

  useEffect(() => {
    const cosmos = cosmosRef.current
    if (!cosmos) return

    payloadRef.current = payload
    cosmos.setPointPositions(payload.positions)
    cosmos.setPointColors(payload.pointColors)
    cosmos.setPointSizes(payload.pointSizes)
    applyEdgeDensity(true)
    window.setTimeout(() => {
      cosmos.fitView(0, 0.18)
    }, 0)

    if (selectedNode && level !== 'person') {
      focusNode(selectedNode, false)
    } else if (level === 'global') {
      window.setTimeout(() => {
        focusNode(DEFAULT_FOCUS_NODE_ID, true)
      }, 160)
    } else if (level === 'person') {
      window.setTimeout(() => {
        cosmos.fitView(260, 0.28)
      }, 120)
    }
  }, [applyEdgeDensity, focusNode, level, payload, selectedNode])

  useEffect(() => {
    if (!navigateToNodeRef) return
    navigateToNodeRef.current = async (nodeId: string) => {
      if (focusNode(nodeId, true)) return
      if (level === 'l1') return

      const data = await loadLevel('l1')
      if (!data.nodes.some(node => node.id === nodeId)) return

      swapGraph(graph, data, 'l1')
      onLevelChange('l1')
      window.setTimeout(() => {
        focusNode(nodeId, true)
      }, 80)
    }
  }, [focusNode, graph, level, navigateToNodeRef, onLevelChange])

  const hoveredLabel = hoveredNode && graph.hasNode(hoveredNode)
    ? graph.getNodeAttribute(hoveredNode, 'label')
    : null

  return (
    <div className="relative w-full h-full bg-[#0a0a0f]">
      <div ref={containerRef} className="w-full h-full" />
      <div className="absolute bottom-4 left-4 z-20 rounded border border-cyan-400/20 bg-black/45 px-3 py-2 text-xs text-slate-400 backdrop-blur">
        <div className="font-medium text-cyan-200">Cosmos.gl WebGL POC</div>
        <div>{payload.nodeIds.length.toLocaleString()} people · {visibleEdgeCount.toLocaleString()} / {payload.edgeRecords.length.toLocaleString()} edges</div>
        <div>Zoom LOD: shared works at least {edgeCutoff}</div>
        <div>{hoveredLabel ? `Hover: ${hoveredLabel}` : level === 'person' ? 'Centered on one person and direct collaborators' : 'Labels are intentionally deferred for global density'}</div>
      </div>
    </div>
  )
}
