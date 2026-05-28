import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Graph as CosmosGraph } from '@cosmos.gl/graph'
import Graph from 'graphology'
import type { Level } from '../data/loader'
import { displayPersonName } from '../data/personNames'
import type { PersonNameMode } from '../types'
import { recordRuntimeMetric } from '../data/runtimeMetrics'

interface CosmosGalaxyViewProps {
  graph: Graph
  onNodeClick: (nodeId: string) => void
  level: Level
  selectedNode: string | null
  personNameMode: PersonNameMode
  minSharedFloor?: number
  onBackToGlobal: () => void
}

interface CosmosPayload {
  nodeIds: string[]
  positions: Float32Array
  pointColors: Float32Array
  pointSizes: Float32Array
  edgeRecords: EdgeRecord[]
  nodeLabels: Map<string, string>
  priorityLabelIndices: number[]
}

interface EdgeRecord {
  sourceIndex: number
  targetIndex: number
  sharedWorksCount: number
  collaborationScore: number
}

interface PriorityLabel {
  id: string
  label: string
  x: number
  y: number
}

const SEARCH_ZOOM_SCALE = 3.8
const COSMOS_SPACE_SIZE = 8192
const COSMOS_LAYOUT_SIZE = 4300
const PRIORITY_LABEL_LIMIT: Record<Level, number> = {
  global: 10,
  l0: 12,
  l1: 12,
  person: 8,
}
const PRIORITY_LABEL_SPACING: Record<Level, number> = {
  global: 520,
  l0: 440,
  l1: 360,
  person: 280,
}

function readRgb(value: unknown): [number, number, number] {
  if (typeof value !== 'string') return [212, 215, 223]
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!match) return [212, 215, 223]
  return [Number(match[1]), Number(match[2]), Number(match[3])]
}

function minSharedForZoom(level: Level, zoom: number, minSharedFloor = 1): number {
  if (level === 'person') return minSharedFloor

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

    const score = edge.collaborationScore > 0 ? edge.collaborationScore : edge.sharedWorksCount
    const t = Math.min(1, Math.log10(1 + score) / 2.2)

    const r = 130 + t * 80
    const g = 148 + t * 65
    const b = 175 + t * 55
    linkColors[index * 4] = r
    linkColors[index * 4 + 1] = g
    linkColors[index * 4 + 2] = b

    const alpha = level === 'person'
      ? 28 + t * 52
      : level === 'global'
        ? 10 + t * 22
        : 8 + t * 20
    linkColors[index * 4 + 3] = alpha

    linkWidths[index] = level === 'person'
      ? 0.18 + t * 0.6
      : level === 'global'
        ? 0.08 + t * 0.32
        : 0.06 + t * 0.22
  })

  return { links, linkColors, linkWidths, visibleEdgeCount: visibleEdges.length }
}

function buildCosmosPayload(graph: Graph, personNameMode: PersonNameMode, level: Level): CosmosPayload {
  const nodeIds = graph.nodes()
  const indexById = new Map(nodeIds.map((id, index) => [id, index]))
  const positions = new Float32Array(nodeIds.length * 2)
  const rawPositions = new Float32Array(nodeIds.length * 2)
  const pointColors = new Float32Array(nodeIds.length * 4)
  const pointSizes = new Float32Array(nodeIds.length)
  const nodeLabels = new Map<string, string>()
  const labelCandidates: { index: number; score: number }[] = []

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
      ? 10
      : Math.max(2.0, Number(attrs.size ?? 2.5) * (graph.order <= 700 ? 1.2 : 1.0))

    const name = (attrs.name as string) ?? (attrs.label as string) ?? nodeId
    const nameCn = attrs.nameCn as string | undefined
    const nameTw = attrs.nameTw as string | undefined
    nodeLabels.set(nodeId, displayPersonName({ name, nameCn, nameTw }, personNameMode))

    const weightedDegree = Number(attrs.visibleWeightedDegree ?? 0)
    const degree = Number(attrs.degree ?? 0)
    const sharedWorksCount = Number(attrs.sharedWorksCount ?? 0)
    const centerBoost = attrs.isCenter ? 1_000_000 : 0
    const score = level === 'person'
      ? centerBoost + sharedWorksCount * 1000 + weightedDegree
      : weightedDegree || degree
    labelCandidates.push({ index, score })
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
    const collaborationScore = Number(graph.getEdgeAttribute(edge, 'collaborationScore') ?? 0)
    return {
      sourceIndex: indexById.get(source) ?? 0,
      targetIndex: indexById.get(target) ?? 0,
      sharedWorksCount,
      collaborationScore,
    }
  })

  const priorityLabelIndices: number[] = []
  const minLabelDistance = PRIORITY_LABEL_SPACING[level]
  const sortedLabelCandidates = labelCandidates
    .filter(candidate => candidate.score > 0)
    .sort((a, b) => b.score - a.score)

  for (const candidate of sortedLabelCandidates) {
    const x = positions[candidate.index * 2]
    const y = positions[candidate.index * 2 + 1]
    const isFarEnough = priorityLabelIndices.every(index => {
      const dx = positions[index * 2] - x
      const dy = positions[index * 2 + 1] - y
      return dx * dx + dy * dy >= minLabelDistance * minLabelDistance
    })
    if (!isFarEnough) continue

    priorityLabelIndices.push(candidate.index)
    if (priorityLabelIndices.length >= PRIORITY_LABEL_LIMIT[level]) break
  }

  return { nodeIds, positions, pointColors, pointSizes, edgeRecords, nodeLabels, priorityLabelIndices }
}

const COSMOS_CONFIG = {
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
  hoveredPointRingColor: '#f8fafc',
  focusedPointRingColor: '#fef08a',
  pointDefaultColor: '#cbd5e1',
  pointGreyoutOpacity: 0.03,
  pointOpacity: 0.92,
  pointSizeScale: 0.85,
  linkDefaultColor: [148, 163, 184, 0.1] as [number, number, number, number],
  linkGreyoutOpacity: 0.04,
  linkOpacity: 1,
  linkVisibilityDistanceRange: [35, 180],
  linkVisibilityMinTransparency: 0.02,
  scalePointsOnZoom: true,
  scaleLinksOnZoom: false,
  pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
  attribution: '',
}

export function CosmosGalaxyView({
  graph,
  onNodeClick,
  level,
  selectedNode,
  personNameMode,
  minSharedFloor = 1,
  onBackToGlobal,
}: CosmosGalaxyViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cosmosRef = useRef<CosmosGraph | null>(null)
  const payloadRef = useRef<CosmosPayload | null>(null)
  const selectedNodeRef = useRef<string | null>(selectedNode)
  const edgeCutoffRef = useRef(minSharedForZoom(level, 1, minSharedFloor))
  const applyEdgeDensityRef = useRef<(() => void) | null>(null)
  const hoverLabelRef = useRef<HTMLDivElement | null>(null)
  const hoveredNodeRef = useRef<string | null>(null)
  const [visibleEdgeCount, setVisibleEdgeCount] = useState(0)
  const [edgeCutoff, setEdgeCutoff] = useState(() => minSharedForZoom(level, 1, minSharedFloor))
  const [priorityLabels, setPriorityLabels] = useState<PriorityLabel[]>([])
  const payload = useMemo(() => buildCosmosPayload(graph, personNameMode, level), [graph, level, personNameMode])

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

    const nextCutoff = minSharedForZoom(level, cosmos.getZoomLevel(), minSharedFloor)
    if (!force && edgeCutoffRef.current === nextCutoff) return

    const arrays = buildEdgeArrays(payload.edgeRecords, nextCutoff, level)
    cosmos.setLinks(arrays.links)
    cosmos.setLinkColors(arrays.linkColors)
    cosmos.setLinkWidths(arrays.linkWidths)
    cosmos.render()

    edgeCutoffRef.current = nextCutoff
    setEdgeCutoff(nextCutoff)
    setVisibleEdgeCount(arrays.visibleEdgeCount)
  }, [level, minSharedFloor])

  const updatePriorityLabels = useCallback(() => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const container = containerRef.current
    if (!cosmos || !payload || !container) {
      setPriorityLabels([])
      return
    }

    const bounds = container.getBoundingClientRect()
    const labels: PriorityLabel[] = []
    const boxes: { left: number; right: number; top: number; bottom: number }[] = []
    for (const index of payload.priorityLabelIndices) {
      const label = payload.nodeLabels.get(payload.nodeIds[index]) ?? payload.nodeIds[index]
      const [x, y] = cosmos.spaceToScreenPosition([
        payload.positions[index * 2],
        payload.positions[index * 2 + 1],
      ])
      const width = Math.min(180, Math.max(52, label.length * 12 + 18))
      const box = {
        left: x - width / 2,
        right: x + width / 2,
        top: y - 28,
        bottom: y - 4,
      }
      if (box.left < 8 || box.top < 76 || box.right > bounds.width - 8 || box.bottom > bounds.height - 8) continue
      if (boxes.some(existing => (
        box.left < existing.right
        && box.right > existing.left
        && box.top < existing.bottom
        && box.bottom > existing.top
      ))) continue

      boxes.push(box)
      labels.push({
        id: payload.nodeIds[index],
        label,
        x,
        y,
      })
    }
    setPriorityLabels(labels)
  }, [])

  // Stable show/hide hover label via DOM — avoids React re-renders on every hover.
  const showHoverLabel = useCallback((nodeId: string | null) => {
    hoveredNodeRef.current = nodeId
    const el = hoverLabelRef.current
    if (!el) return

    if (nodeId) {
      const label = payloadRef.current?.nodeLabels.get(nodeId) ?? nodeId
      el.textContent = label
      el.classList.remove('opacity-0')
    } else {
      el.classList.add('opacity-0')
    }
  }, [])

  useEffect(() => {
    applyEdgeDensityRef.current = () => applyEdgeDensity()
  }, [applyEdgeDensity])

  useEffect(() => {
    const handleResize = () => updatePriorityLabels()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [updatePriorityLabels])

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
      ...COSMOS_CONFIG,
      onPointClick: (index: number) => {
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
      onPointMouseOver: (index: number) => {
        showHoverLabel(payloadRef.current?.nodeIds[index] ?? null)
      },
      onPointMouseOut: () => {
        showHoverLabel(null)
      },
      onZoomEnd: () => {
        applyEdgeDensityRef.current?.()
        updatePriorityLabels()
      },
      onDragEnd: () => {
        updatePriorityLabels()
      },
    })

    cosmosRef.current = cosmos
    return () => {
      cosmos.destroy()
      cosmosRef.current = null
    }
  }, [focusNode, onNodeClick, showHoverLabel, updatePriorityLabels])

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
      window.requestAnimationFrame(updatePriorityLabels)
    }, 0)

    if (selectedNode && level !== 'person') {
      focusNode(selectedNode, false)
    } else if (level === 'person') {
      window.setTimeout(() => {
        cosmos.fitView(260, 0.28)
        window.setTimeout(updatePriorityLabels, 280)
      }, 120)
    }

    window.requestAnimationFrame(() => {
      const visibleEdges = payload.edgeRecords.filter(
        edge => edge.sharedWorksCount >= edgeCutoffRef.current,
      ).length
      recordRuntimeMetric('cosmos-ready', {
        level,
        nodes: payload.nodeIds.length,
        totalEdges: payload.edgeRecords.length,
        visibleEdges,
        edgeCutoff: edgeCutoffRef.current,
      })
      updatePriorityLabels()
    })
  }, [applyEdgeDensity, focusNode, level, payload, selectedNode, updatePriorityLabels])

  const centerNodeName = level === 'person' && selectedNode && graph.hasNode(selectedNode)
    ? displayPersonName(
      {
        name: graph.getNodeAttribute(selectedNode, 'name'),
        nameCn: graph.getNodeAttribute(selectedNode, 'nameCn'),
        nameTw: graph.getNodeAttribute(selectedNode, 'nameTw'),
      },
      personNameMode,
    )
    : null

  return (
    <div className="relative w-full h-full bg-[#0a0a0f]">
      <div ref={containerRef} className="w-full h-full" />

      {/* Hover label — DOM-only, no React re-render on hover */}
      <div
        ref={hoverLabelRef}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[140%] z-20 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-600/50 text-sm text-slate-100 backdrop-blur shadow-lg pointer-events-none whitespace-nowrap opacity-0 transition-opacity duration-75"
      />

      <div className="pointer-events-none absolute inset-0 z-10">
        {priorityLabels.map(label => (
          <div
            key={label.id}
            className="absolute -translate-x-1/2 -translate-y-[150%] rounded-full border border-slate-600/40 bg-slate-950/65 px-2 py-0.5 text-[11px] leading-tight text-slate-300 shadow-[0_4px_18px_rgba(0,0,0,0.35)] backdrop-blur"
            style={{ left: label.x, top: label.y }}
          >
            {label.label}
          </div>
        ))}
      </div>

      <div className="absolute bottom-4 left-4 z-20 rounded border border-slate-700/60 bg-black/50 px-3 py-2 text-xs text-slate-400 backdrop-blur">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          <span className="text-slate-300 font-medium">
            {payload.nodeIds.length.toLocaleString()} people
          </span>
          <span className="text-slate-600">·</span>
          <span>{visibleEdgeCount.toLocaleString()} / {payload.edgeRecords.length.toLocaleString()} edges</span>
        </div>
        <div className="text-slate-500">
          min shared works: {edgeCutoff}
        </div>
      </div>

      {level === 'person' && (
        <div className="absolute bottom-20 left-4 z-20">
          <button
            type="button"
            onClick={onBackToGlobal}
            className="flex items-center gap-1.5 rounded border border-cyan-500/40 bg-cyan-950/70 px-4 py-2 text-sm text-cyan-200 backdrop-blur hover:bg-cyan-900/70 hover:border-cyan-400/60 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-9 9 9" />
              <path d="M12 3v14" />
              <path d="M5 13v7h14v-7" />
            </svg>
            {centerNodeName ? `${centerNodeName} · ` : ''}返回全量星系
          </button>
        </div>
      )}
    </div>
  )
}
