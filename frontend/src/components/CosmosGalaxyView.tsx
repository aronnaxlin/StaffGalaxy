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
  onBackToGlobal: () => void
}

interface CosmosPayload {
  nodeIds: string[]
  nodeIndexById: Map<string, number>
  positions: Float32Array
  pointColors: Float32Array
  pointSizes: Float32Array
  // Edges sorted descending by strength (sharedWorksCount, then collaborationScore).
  // Any zoom-dependent edge budget is therefore a zero-copy prefix `.subarray()` —
  // no per-frame filter/rebuild, unlike the pre-v3 buildEdgeArrays() approach.
  sortedLinks: Float32Array
  sortedLinkColors: Float32Array
  sortedLinkWidths: Float32Array
  sortedSharedCounts: Int32Array
  totalEdgeCount: number
  // Point index -> indices into the sorted edge arrays incident to that point.
  // Built once so hover highlighting is O(degree): cosmos.gl's own
  // getConnectedLinkIndices(pointIndices) requires BOTH endpoints of a link to
  // be in the given set ("edges within a selection"), which returns nothing
  // useful for a single hovered point — this is our own incident-edge index.
  pointToLinkIndices: number[][]
  nodeLabels: Map<string, string>
  defaultLabelIndices: number[]
}

interface EdgeRecord {
  sourceIndex: number
  targetIndex: number
  sharedWorksCount: number
  collaborationScore: number
}

interface GraphLabel {
  id: string
  label: string
  x: number
  y: number
}

const SEARCH_ZOOM_SCALE = 3.8
const COSMOS_SPACE_SIZE = 8192
const COSMOS_LAYOUT_SIZE = 4300
const PERSON_ALL_LABEL_EDGE_LIMIT = 36

// cosmos.gl v3 expects RGBA channels normalized to [0, 1] for setPointColors/
// setLinkColors (was RGB 0-255 / alpha 0-1 in v2). See migration-notes.md.
function readRgbNormalized(value: unknown): [number, number, number] {
  if (typeof value !== 'string') return [212 / 255, 215 / 255, 223 / 255]
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!match) return [212 / 255, 215 / 255, 223 / 255]
  return [Number(match[1]) / 255, Number(match[2]) / 255, Number(match[3]) / 255]
}

// Edge count to keep on screen at the current zoom level, taken as a prefix of the
// strength-sorted edge arrays. Verified against the real dump-2026-06-30
// snapshot (renders correctly, no errors at 60,000/372,661 edges) but not
// rigorously frame-rate-profiled during pan/zoom — retune against
// reports/graph-performance.md once that's measured.
function edgeBudgetForZoom(level: Level, zoom: number, totalEdgeCount: number): number {
  if (level === 'person') return totalEdgeCount

  if (level === 'global') {
    if (zoom > 0.9) return 6_000
    if (zoom > 0.65) return 20_000
    return 60_000
  }

  if (zoom > 0.8) return 20_000
  if (zoom > 0.55) return 50_000
  return 90_000
}

function buildCosmosPayload(graph: Graph, personNameMode: PersonNameMode, level: Level): CosmosPayload {
  const nodeIds = graph.nodes()
  const indexById = new Map(nodeIds.map((id, index) => [id, index]))
  const positions = new Float32Array(nodeIds.length * 2)
  const rawPositions = new Float32Array(nodeIds.length * 2)
  const pointColors = new Float32Array(nodeIds.length * 4)
  const pointSizes = new Float32Array(nodeIds.length)
  const nodeLabels = new Map<string, string>()

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity

  nodeIds.forEach((nodeId, index) => {
    const attrs = graph.getNodeAttributes(nodeId)
    const x = Number(attrs.x ?? 0)
    const y = Number(attrs.y ?? 0)
    rawPositions[index * 2] = x
    rawPositions[index * 2 + 1] = y
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y

    const [r, g, b] = readRgbNormalized(attrs.color)
    pointColors[index * 4] = r
    pointColors[index * 4 + 1] = g
    pointColors[index * 4 + 2] = b
    pointColors[index * 4 + 3] = 1
    pointSizes[index] = attrs.isCenter
      ? 10
      : Math.max(2.0, Number(attrs.size ?? 2.5) * (graph.order <= 700 ? 1.2 : 1.0))

    const name = (attrs.name as string) ?? (attrs.label as string) ?? nodeId
    const nameCn = attrs.nameCn as string | undefined
    const nameTw = attrs.nameTw as string | undefined
    nodeLabels.set(nodeId, displayPersonName({ name, nameCn, nameTw }, personNameMode))
  })

  const span = Math.max(maxX - minX, maxY - minY, 1)
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2

  nodeIds.forEach((_nodeId, index) => {
    positions[index * 2] = COSMOS_SPACE_SIZE / 2 + ((rawPositions[index * 2] - centerX) / span) * COSMOS_LAYOUT_SIZE
    positions[index * 2 + 1] = COSMOS_SPACE_SIZE / 2 + ((rawPositions[index * 2 + 1] - centerY) / span) * COSMOS_LAYOUT_SIZE
  })

  const edgeRecords: EdgeRecord[] = graph.edges().map(edge => {
    const [source, target] = graph.extremities(edge)
    return {
      sourceIndex: indexById.get(source) ?? 0,
      targetIndex: indexById.get(target) ?? 0,
      sharedWorksCount: Number(graph.getEdgeAttribute(edge, 'sharedWorksCount') ?? 0),
      collaborationScore: Number(graph.getEdgeAttribute(edge, 'collaborationScore') ?? 0),
    }
  })
  // Sort descending by strength so any zoom-dependent edge budget is a prefix slice.
  edgeRecords.sort((a, b) => (
    b.sharedWorksCount - a.sharedWorksCount || b.collaborationScore - a.collaborationScore
  ))

  const totalEdgeCount = edgeRecords.length
  const sortedLinks = new Float32Array(totalEdgeCount * 2)
  const sortedLinkColors = new Float32Array(totalEdgeCount * 4)
  const sortedLinkWidths = new Float32Array(totalEdgeCount)
  const sortedSharedCounts = new Int32Array(totalEdgeCount)

  edgeRecords.forEach((edge, index) => {
    sortedLinks[index * 2] = edge.sourceIndex
    sortedLinks[index * 2 + 1] = edge.targetIndex
    sortedSharedCounts[index] = edge.sharedWorksCount

    const score = edge.collaborationScore > 0 ? edge.collaborationScore : edge.sharedWorksCount
    const t = Math.min(1, Math.log10(1 + score) / 2.2)

    const r = 130 + t * 80
    const g = 148 + t * 65
    const b = 175 + t * 55
    const alpha = level === 'person'
      ? 28 + t * 52
      : level === 'global'
        ? 10 + t * 22
        : 8 + t * 20

    sortedLinkColors[index * 4] = r / 255
    sortedLinkColors[index * 4 + 1] = g / 255
    sortedLinkColors[index * 4 + 2] = b / 255
    sortedLinkColors[index * 4 + 3] = alpha / 255

    sortedLinkWidths[index] = level === 'l1'
      ? 0.1 + t * 0.3
      : level === 'person'
        ? 0.2 + t * 0.55
        : 0.14 + t * 0.44
  })

  const pointToLinkIndices: number[][] = nodeIds.map(() => [])
  edgeRecords.forEach((edge, index) => {
    pointToLinkIndices[edge.sourceIndex].push(index)
    pointToLinkIndices[edge.targetIndex].push(index)
  })

  const centerIndex = nodeIds.findIndex(nodeId => Boolean(graph.getNodeAttribute(nodeId, 'isCenter')))
  const defaultLabelIndices = level !== 'person'
    ? []
    : totalEdgeCount <= PERSON_ALL_LABEL_EDGE_LIMIT
      ? nodeIds.map((_nodeId, index) => index)
      : centerIndex >= 0
        ? [centerIndex]
        : []

  return {
    nodeIds,
    nodeIndexById: indexById,
    positions,
    pointColors,
    pointSizes,
    sortedLinks,
    sortedLinkColors,
    sortedLinkWidths,
    sortedSharedCounts,
    totalEdgeCount,
    pointToLinkIndices,
    nodeLabels,
    defaultLabelIndices,
  }
}

const COSMOS_CONFIG = {
  backgroundColor: '#0a0a0f',
  enableSimulation: false,
  // Keep v2's instant-snap updates; v3 defaults to 800ms animated transitions on
  // position/color/size/width changes, which would visibly lag every LOD/hover step.
  transitionDuration: 0,
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
  linkDefaultColor: [148 / 255, 163 / 255, 184 / 255, 0.1] as [number, number, number, number],
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
  onBackToGlobal,
}: CosmosGalaxyViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cosmosRef = useRef<CosmosGraph | null>(null)
  const payloadRef = useRef<CosmosPayload | null>(null)
  const selectedNodeRef = useRef<string | null>(selectedNode)
  const edgeCountRef = useRef(0)
  const applyEdgeDensityRef = useRef<(() => void) | null>(null)
  const hoverLabelRef = useRef<HTMLDivElement | null>(null)
  const hoveredNodeRef = useRef<string | null>(null)
  const lastPointerPositionRef = useRef<[number, number] | null>(null)
  const highlightedPointerPositionRef = useRef<[number, number] | null>(null)
  const [visibleEdgeCount, setVisibleEdgeCount] = useState(0)
  const [edgeCutoff, setEdgeCutoff] = useState(0)
  const [defaultLabels, setDefaultLabels] = useState<GraphLabel[]>([])
  const payload = useMemo(() => buildCosmosPayload(graph, personNameMode, level), [graph, level, personNameMode])

  const focusNode = useCallback((nodeId: string, animate = true) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return false

    const index = payload.nodeIds.indexOf(nodeId)
    if (index < 0) return false

    cosmos.setConfigPartial({ focusedPointIndex: index })
    // Explicit enableSimulation=false: this layout is static/precomputed, and letting
    // the zoom transition run physics (v3 default) would drift points during the animation.
    if (animate) cosmos.zoomToPointByIndex(index, 420, SEARCH_ZOOM_SCALE, false, false)
    return true
  }, [])

  const applyEdgeDensity = useCallback((force = false) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return

    const zoom = cosmos.getZoomLevel()
    const budget = edgeBudgetForZoom(level, zoom, payload.totalEdgeCount)
    const n = Math.min(budget, payload.totalEdgeCount)
    if (!force && n === edgeCountRef.current) return

    // Zero-copy prefix slices — no per-frame filter/allocation/GC pressure.
    cosmos.setLinks(payload.sortedLinks.subarray(0, n * 2))
    cosmos.setLinkColors(payload.sortedLinkColors.subarray(0, n * 4))
    cosmos.setLinkWidths(payload.sortedLinkWidths.subarray(0, n))
    cosmos.render()

    edgeCountRef.current = n
    setVisibleEdgeCount(n)
    setEdgeCutoff(n > 0 ? payload.sortedSharedCounts[n - 1] : 0)
  }, [level])

  // Hover highlight is pure GPU-side config (v3 highlightedPointIndices /
  // highlightedLinkIndices) driven by the precomputed pointToLinkIndices
  // incidence map — O(degree), not O(edges). (cosmos.gl's own
  // getConnectedLinkIndices requires BOTH endpoints in the given set, so it
  // can't answer "edges touching this one point" — see CosmosPayload comment.)
  const applyHoverEdgeFocus = useCallback((index?: number) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload || level === 'person') return

    if (index === undefined) {
      cosmos.setConfigPartial({ highlightedPointIndices: undefined, highlightedLinkIndices: undefined })
      return
    }

    const visibleCount = edgeCountRef.current
    const linkIndices = (payload.pointToLinkIndices[index] ?? []).filter(li => li < visibleCount)
    const neighborIndices = linkIndices.map(li => {
      const source = payload.sortedLinks[li * 2]
      const target = payload.sortedLinks[li * 2 + 1]
      return source === index ? target : source
    })
    cosmos.setConfigPartial({
      highlightedPointIndices: [index, ...neighborIndices],
      highlightedLinkIndices: linkIndices,
    })
  }, [level])

  const updateDefaultLabels = useCallback(() => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const container = containerRef.current
    if (!cosmos || !payload || !container) {
      setDefaultLabels([])
      return
    }
    if (payload.defaultLabelIndices.length === 0) {
      setDefaultLabels(current => current.length > 0 ? [] : current)
      return
    }

    const bounds = container.getBoundingClientRect()
    const labels: GraphLabel[] = []
    const boxes: { left: number; right: number; top: number; bottom: number }[] = []
    const showAllPersonalLabels = level === 'person' && payload.defaultLabelIndices.length > 1
    for (const index of payload.defaultLabelIndices) {
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
      if (!showAllPersonalLabels && boxes.some(existing => (
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
    setDefaultLabels(labels)
  }, [level])

  const updateHoverLabelPosition = useCallback((nodeId = hoveredNodeRef.current) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const el = hoverLabelRef.current
    if (!cosmos || !payload || !el || !nodeId) return

    const index = payload.nodeIndexById.get(nodeId)
    if (index === undefined) return
    const [x, y] = cosmos.spaceToScreenPosition([
      payload.positions[index * 2],
      payload.positions[index * 2 + 1],
    ])
    el.style.left = `${x}px`
    el.style.top = `${y}px`
  }, [])

  // Stable show/hide hover label via DOM — avoids React re-renders on every hover.
  const showHoverLabel = useCallback((nodeId: string | null) => {
    hoveredNodeRef.current = nodeId
    const el = hoverLabelRef.current
    if (!el) return

    if (nodeId) {
      const label = payloadRef.current?.nodeLabels.get(nodeId) ?? nodeId
      el.textContent = label
      updateHoverLabelPosition(nodeId)
      el.classList.remove('opacity-0')
    } else {
      el.classList.add('opacity-0')
    }
  }, [updateHoverLabelPosition])

  const clearHoverEdgeFocus = useCallback(() => {
    highlightedPointerPositionRef.current = null
    showHoverLabel(null)
    applyHoverEdgeFocus()
  }, [applyHoverEdgeFocus, showHoverLabel])

  useEffect(() => {
    applyEdgeDensityRef.current = () => applyEdgeDensity()
  }, [applyEdgeDensity])

  useEffect(() => {
    const handleResize = () => {
      updateDefaultLabels()
      updateHoverLabelPosition()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [updateDefaultLabels, updateHoverLabelPosition])

  useEffect(() => {
    selectedNodeRef.current = selectedNode
    if (!selectedNode) {
      cosmosRef.current?.setConfigPartial({ focusedPointIndex: undefined })
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
        cosmos.setConfigPartial({ focusedPointIndex: undefined })
      },
      onPointMouseOver: (index: number) => {
        highlightedPointerPositionRef.current = lastPointerPositionRef.current
        showHoverLabel(payloadRef.current?.nodeIds[index] ?? null)
        applyHoverEdgeFocus(index)
      },
      onPointMouseOut: () => {
        clearHoverEdgeFocus()
      },
      onMouseMove: (_index: number | undefined, _position: [number, number] | undefined, event: MouseEvent) => {
        const nextPosition: [number, number] = [event.offsetX, event.offsetY]
        const highlightedPosition = highlightedPointerPositionRef.current
        if (highlightedPosition) {
          const dx = nextPosition[0] - highlightedPosition[0]
          const dy = nextPosition[1] - highlightedPosition[1]
          if (dx * dx + dy * dy > 36) clearHoverEdgeFocus()
        }
        lastPointerPositionRef.current = nextPosition
      },
      onZoomEnd: () => {
        applyEdgeDensityRef.current?.()
        updateDefaultLabels()
        updateHoverLabelPosition()
      },
      onZoom: () => {
        updateDefaultLabels()
        updateHoverLabelPosition()
      },
      onDrag: () => {
        updateDefaultLabels()
        updateHoverLabelPosition()
      },
      onDragEnd: () => {
        updateDefaultLabels()
        updateHoverLabelPosition()
      },
    })

    cosmosRef.current = cosmos
    return () => {
      cosmos.destroy()
      cosmosRef.current = null
    }
  }, [applyHoverEdgeFocus, clearHoverEdgeFocus, focusNode, onNodeClick, showHoverLabel, updateDefaultLabels, updateHoverLabelPosition])

  useEffect(() => {
    const cosmos = cosmosRef.current
    if (!cosmos) return

    payloadRef.current = payload
    cosmos.setPointPositions(payload.positions)
    cosmos.setPointColors(payload.pointColors)
    cosmos.setPointSizes(payload.pointSizes)
    applyEdgeDensity(true)
    window.setTimeout(() => {
      cosmos.fitView(0, 0.18, false)
      window.requestAnimationFrame(updateDefaultLabels)
    }, 0)

    if (selectedNode && level !== 'person') {
      focusNode(selectedNode, false)
    } else if (level === 'person') {
      window.setTimeout(() => {
        cosmos.fitView(260, 0.28, false)
        window.setTimeout(updateDefaultLabels, 280)
      }, 120)
    }

    window.requestAnimationFrame(() => {
      recordRuntimeMetric('cosmos-ready', {
        level,
        nodes: payload.nodeIds.length,
        totalEdges: payload.totalEdgeCount,
        visibleEdges: edgeCountRef.current,
        edgeCutoff: edgeCountRef.current > 0 ? payload.sortedSharedCounts[edgeCountRef.current - 1] : 0,
      })
      updateDefaultLabels()
    })
  }, [applyEdgeDensity, focusNode, level, payload, selectedNode, updateDefaultLabels])

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
      <div ref={containerRef} className="w-full h-full" onMouseLeave={clearHoverEdgeFocus} />

      {/* Hover label — DOM-only, no React re-render on hover */}
      <div
        ref={hoverLabelRef}
        className="absolute -translate-x-1/2 -translate-y-[140%] z-20 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-600/50 text-sm text-slate-100 backdrop-blur shadow-lg pointer-events-none whitespace-nowrap opacity-0 transition-opacity duration-75"
      />

      <div className="pointer-events-none absolute inset-0 z-10">
        {defaultLabels.map(label => (
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
          <span>{visibleEdgeCount.toLocaleString()} / {payload.totalEdgeCount.toLocaleString()} edges</span>
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
