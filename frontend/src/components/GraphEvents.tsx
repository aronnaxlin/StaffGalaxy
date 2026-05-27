import { useEffect, useCallback, useRef } from 'react'
import { useSigma } from '@react-sigma/core'
import { loadLevel, type Level } from '../data/loader'
import { swapGraph } from '../data/graphBuilder'

interface GraphEventsProps {
  onNodeClick: (nodeId: string) => void
  hoveredNode: string | null
  setHoveredNode: (id: string | null) => void
  level: Level
  onLevelChange: (level: Level) => void
  selectedNode: string | null
}

// Sigma normalized coords: ratio≈1 = full graph fits, smaller = zoomed in.
// Use hysteresis so trackpads do not bounce between L0/L1 around one boundary.
const ENTER_L1_RATIO = 0.38
const EXIT_L1_RATIO = 0.72
const ZOOM_DEBOUNCE_MS = 320
const HOVER_NEIGHBOR_LIMIT = 90
const HOVER_LABEL_LIMIT = 24

function getDesiredLevel(ratio: number, current: Level): Level {
  if (current === 'l0') return ratio < ENTER_L1_RATIO ? 'l1' : 'l0'
  return ratio > EXIT_L1_RATIO ? 'l0' : 'l1'
}

function minSharedForCamera(ratio: number, level: Level): number {
  if (level === 'l0') {
    if (ratio > 0.6) return 12
    if (ratio > 0.45) return 10
    if (ratio > ENTER_L1_RATIO) return 8
    return 5
  }

  if (ratio > 0.45) return 12
  if (ratio > 0.25) return 9
  return 6
}

export function GraphEvents({
  onNodeClick,
  hoveredNode,
  setHoveredNode,
  level,
  onLevelChange,
  selectedNode,
}: GraphEventsProps) {
  const sigma = useSigma()
  const focusedNodeRef = useRef<string | null>(null)
  const debounceTimerRef = useRef<number | null>(null)
  const levelRef = useRef<Level>(level)
  const switchingRef = useRef(false)
  const edgeCutoffRef = useRef<number | null>(null)

  const applyDefaultEdgeFilter = useCallback((force = false) => {
    if (focusedNodeRef.current) return

    const cutoff = minSharedForCamera(sigma.getCamera().ratio, levelRef.current)
    if (!force && edgeCutoffRef.current === cutoff) return
    edgeCutoffRef.current = cutoff

    sigma.setSetting('edgeReducer', (_edge, data) => {
      const sharedWorksCount = Number(data.sharedWorksCount ?? 0)
      if (sharedWorksCount < cutoff) return { ...data, hidden: true }
      return data
    })
  }, [sigma])

  useEffect(() => {
    levelRef.current = level
    applyDefaultEdgeFilter(true)
  }, [applyDefaultEdgeFilter, level])

  // Focus dim — only active for hover/selection, no per-frame cost otherwise.
  const setFocusNode = useCallback((focusNode: string | null) => {
    if (focusedNodeRef.current === focusNode) return
    focusedNodeRef.current = focusNode

    if (!focusNode) {
      sigma.setSetting('nodeReducer', null)
      applyDefaultEdgeFilter(true)
      return
    }

    const graph = sigma.getGraph()
    if (!graph.hasNode(focusNode)) return

    const incidentEdges = graph.edges(focusNode)
      .map(edge => {
        const [source, target] = graph.extremities(edge)
        const neighbor = source === focusNode ? target : source
        return {
          edge,
          neighbor,
          sharedWorksCount: Number(graph.getEdgeAttribute(edge, 'sharedWorksCount') ?? 0),
        }
      })
      .sort((a, b) => b.sharedWorksCount - a.sharedWorksCount)
      .slice(0, HOVER_NEIGHBOR_LIMIT)

    const highlightedEdges = new Set(incidentEdges.map(item => item.edge))
    const highlightedNodes = new Set(incidentEdges.map(item => item.neighbor))
    const labeledNodes = new Set(incidentEdges.slice(0, HOVER_LABEL_LIMIT).map(item => item.neighbor))
    highlightedNodes.add(focusNode)
    labeledNodes.add(focusNode)

    sigma.setSetting('nodeReducer', (node, data) => {
      if (node === focusNode) return { ...data, color: '#fef08a', forceLabel: true, zIndex: 3 }
      if (highlightedNodes.has(node)) {
        return {
          ...data,
          color: '#e5e7eb',
          label: labeledNodes.has(node) ? data.label : '',
          zIndex: 2,
        }
      }
      return { ...data, color: 'rgba(148,163,184,0.08)', label: '' }
    })

    sigma.setSetting('edgeReducer', (edge, data) => {
      if (highlightedEdges.has(edge)) return { ...data, color: 'rgba(226,232,240,0.34)', size: 0.7, zIndex: 1 }
      return { ...data, hidden: true }
    })
  }, [sigma, applyDefaultEdgeFilter])

  useEffect(() => {
    setFocusNode(hoveredNode ?? selectedNode)
  }, [hoveredNode, selectedNode, setFocusNode])

  // Camera zoom → level switch (debounced)
  useEffect(() => {
    const camera = sigma.getCamera()

    const onUpdate = () => {
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = window.setTimeout(() => {
        debounceTimerRef.current = null
        if (switchingRef.current) return

        const ratio = camera.ratio
        const desired = getDesiredLevel(ratio, levelRef.current)
        applyDefaultEdgeFilter()
        if (desired === levelRef.current) return

        switchingRef.current = true
        loadLevel(desired)
          .then(data => {
            // Preserve camera state across swap
            const camState = camera.getState()
            swapGraph(sigma.getGraph(), data, desired)
            camera.setState(camState)
            sigma.refresh()
            levelRef.current = desired
            edgeCutoffRef.current = null
            focusedNodeRef.current = null
            setFocusNode(selectedNode)
            applyDefaultEdgeFilter(true)
            onLevelChange(desired)
          })
          .finally(() => {
            switchingRef.current = false
          })
      }, ZOOM_DEBOUNCE_MS)
    }

    camera.on('updated', onUpdate)
    return () => {
      camera.off('updated', onUpdate)
      if (debounceTimerRef.current !== null) clearTimeout(debounceTimerRef.current)
    }
  }, [sigma, onLevelChange, applyDefaultEdgeFilter, selectedNode, setFocusNode])

  const handleNodeClick = useCallback(({ node }: { node: string }) => onNodeClick(node), [onNodeClick])
  const handleNodeEnter = useCallback(({ node }: { node: string }) => setHoveredNode(node), [setHoveredNode])
  const handleNodeLeave = useCallback(() => setHoveredNode(null), [setHoveredNode])

  useEffect(() => {
    sigma.on('clickNode', handleNodeClick)
    sigma.on('enterNode', handleNodeEnter)
    sigma.on('leaveNode', handleNodeLeave)
    return () => {
      sigma.off('clickNode', handleNodeClick)
      sigma.off('enterNode', handleNodeEnter)
      sigma.off('leaveNode', handleNodeLeave)
    }
  }, [sigma, handleNodeClick, handleNodeEnter, handleNodeLeave])

  return null
}
