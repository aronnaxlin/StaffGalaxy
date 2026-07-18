import { useCallback, useEffect, useRef, useState } from 'react'
import { Graph as CosmosGraph } from '@cosmos.gl/graph'
import type { Level } from '../data/loader'
import type { CosmosPayload } from '../data/cosmosPayload'
import { COSMOS_SPACE_SIZE } from '../data/cosmosPayload'
import { recordRuntimeMetric } from '../data/runtimeMetrics'

interface CosmosGalaxyViewProps {
  payload: CosmosPayload
  onNodeClick: (nodeId: string) => void
  level: Level
  selectedNode: string | null
  onBackToGlobal: () => void
}

interface GraphLabel {
  id: string
  label: string
  x: number
  y: number
}

const SEARCH_ZOOM_SCALE = 3.8

// Edge count to keep on screen at the current zoom level, taken as a prefix of the
// strength-sorted edge arrays. The full 529K-edge set is always resident; these
// tiers only decide how much of it is on the GPU at once.
function edgeBudgetForZoom(level: Level, zoom: number, totalEdgeCount: number): number {
  if (level === 'person') return totalEdgeCount
  if (zoom > 1.1) return 30_000
  if (zoom > 0.75) return 80_000
  return 160_000
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

const MIN_EDGE_BUDGET = 20_000

export function CosmosGalaxyView({
  payload,
  onNodeClick,
  level,
  selectedNode,
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
  const minDegreeRef = useRef(0)
  const edgeBudgetOverrideRef = useRef(0)
  const [visibleEdgeCount, setVisibleEdgeCount] = useState(0)
  const [edgeCutoff, setEdgeCutoff] = useState(0)
  const [defaultLabels, setDefaultLabels] = useState<GraphLabel[]>([])
  const [minDegree, setMinDegree] = useState(0)
  const [edgeBudgetSlider, setEdgeBudgetSlider] = useState(0)

  const focusNode = useCallback((nodeId: string, animate = true) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return false

    const index = payload.nodeIndexById.get(nodeId)
    if (index === undefined) return false

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
    const budget = edgeBudgetOverrideRef.current > 0
      ? edgeBudgetOverrideRef.current
      : edgeBudgetForZoom(level, zoom, payload.totalEdgeCount)
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

  // Base (non-hover) highlight: the min-degree filter dims every point below the
  // threshold via v3 greyout. Hover replaces this with the neighborhood set;
  // mouseout restores it.
  const applyBaseHighlight = useCallback(() => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload || level === 'person') return

    if (minDegreeRef.current <= 0) {
      cosmos.setConfigPartial({ highlightedPointIndices: undefined, highlightedLinkIndices: undefined })
      cosmos.render()
      return
    }
    const threshold = minDegreeRef.current
    const indices: number[] = []
    for (let i = 0; i < payload.degrees.length; i += 1) {
      if (payload.degrees[i] >= threshold) indices.push(i)
    }
    cosmos.setConfigPartial({ highlightedPointIndices: indices, highlightedLinkIndices: undefined })
    cosmos.render()
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
      applyBaseHighlight()
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
  }, [applyBaseHighlight, level])

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
    applyBaseHighlight()
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
  }, [applyBaseHighlight, applyEdgeDensity, focusNode, level, payload, selectedNode, updateDefaultLabels])

  const centerNodeName = level === 'person' && selectedNode
    ? payload.nodeLabels.get(selectedNode) ?? null
    : null

  const edgeBudgetDisplay = edgeBudgetOverrideRef.current > 0
    ? edgeBudgetOverrideRef.current.toLocaleString()
    : 'auto'

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
        {level === 'global' && (
          <div className="mt-2 space-y-2 border-t border-slate-700/50 pt-2">
            <label className="block">
              <span className="flex justify-between gap-4">
                <span>最小度数</span>
                <span className="text-slate-300">{minDegree === 0 ? '关闭' : `≥ ${minDegree}`}</span>
              </span>
              <input
                type="range"
                min={0}
                max={300}
                step={5}
                value={minDegree}
                onChange={event => {
                  const value = Number(event.target.value)
                  setMinDegree(value)
                  minDegreeRef.current = value
                  applyBaseHighlight()
                }}
                className="mt-1 w-44 accent-cyan-400"
              />
            </label>
            <label className="block">
              <span className="flex justify-between gap-4">
                <span>边数预算</span>
                <span className="text-slate-300">{edgeBudgetSlider === 0 ? 'auto' : edgeBudgetDisplay}</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={edgeBudgetSlider}
                onChange={event => {
                  const slider = Number(event.target.value)
                  setEdgeBudgetSlider(slider)
                  if (slider === 0) {
                    edgeBudgetOverrideRef.current = 0
                  } else {
                    const total = payloadRef.current?.totalEdgeCount ?? MIN_EDGE_BUDGET
                    const t = (slider - 1) / 99
                    edgeBudgetOverrideRef.current = Math.round(
                      Math.exp(Math.log(MIN_EDGE_BUDGET) + t * (Math.log(total) - Math.log(MIN_EDGE_BUDGET))),
                    )
                  }
                  applyEdgeDensity(true)
                }}
                className="mt-1 w-44 accent-cyan-400"
              />
            </label>
          </div>
        )}
        <div className="mt-1 text-slate-500">
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
