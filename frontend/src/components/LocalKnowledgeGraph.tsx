import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d'
import { displayPersonName } from '../data/personNames'
import type { KnowledgeGraphNode, PersonKnowledgeGraph, PersonNameMode } from '../types'

// Obsidian-style local graph of the Person-[:CREDITED]->Anime knowledge graph,
// rendered by react-force-graph (d3-force + canvas): drag, zoom/pan, hover and
// idle redraw pausing come from the library; this file only maps data and style.

interface KgNode {
  key: string
  kind: 'person' | 'anime'
  id: string
  label: string
  detail: string
  isCenter: boolean
  val: number
}

interface KgLink {
  source: string
  target: string
  roles: string[]
  weight: number
}

// One accent (amber = the selected person, as in the galaxy); people and works
// are told apart by shape and a neutral vs. cool tone. Links are neutral and
// thicken with role weight; hovered links take the accent.
const ACCENT = '#f5c76b'
const PERSON_COLOR = '#d4d4d8'
const ANIME_COLOR = '#8ab4c9'

function nodeLabel(node: KnowledgeGraphNode, mode: PersonNameMode): string {
  if (node.kind === 'person') return displayPersonName(node, mode)
  return mode !== 'original' && node.nameCn ? node.nameCn : node.name
}

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

function endpointKey(end: string | number | NodeObject<KgNode> | undefined): string {
  return typeof end === 'object' ? (end as KgNode).key : String(end)
}

export function LocalKnowledgeGraph({
  graph,
  personNameMode,
  onSelectPerson,
  onHoverChange,
}: {
  graph: PersonKnowledgeGraph
  personNameMode: PersonNameMode
  onSelectPerson: (personId: string) => void
  onHoverChange?: (key: string | null) => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const graphRef = useRef<ForceGraphMethods<NodeObject<KgNode>, LinkObject<KgNode, KgLink>> | undefined>(undefined)
  // Last positions by key: a new center keeps shared nodes in place, so
  // re-centering reads as one continuous graph instead of a fresh layout.
  const positionsRef = useRef(new Map<string, { x: number; y: number }>())
  const fittedRef = useRef(false)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [hoverKey, setHoverKey] = useState<string | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  const data = useMemo(() => {
    const degree = new Map<string, number>()
    for (const link of graph.links) {
      degree.set(link.source, (degree.get(link.source) ?? 0) + 1)
      degree.set(link.target, (degree.get(link.target) ?? 0) + 1)
    }
    const anchor = positionsRef.current.get(`p:${graph.centerId}`) ?? { x: 0, y: 0 }
    const nodes = graph.nodes.map((node): NodeObject<KgNode> => {
      const known = positionsRef.current.get(node.key)
      const isCenter = node.kind === 'person' && node.isCenter
      return {
        key: node.key,
        kind: node.kind,
        id: node.id,
        label: nodeLabel(node, personNameMode),
        detail: node.kind === 'anime'
          ? `${node.year ?? '年份未知'} · 动画`
          : isCenter ? '中心人物' : `合作 ${node.sharedWorksCount ?? 0} 部`,
        isCenter,
        val: isCenter ? 7 : 1 + (degree.get(node.key) ?? 0) * 0.35,
        x: known?.x ?? anchor.x + (Math.random() - 0.5) * 40,
        y: known?.y ?? anchor.y + (Math.random() - 0.5) * 40,
      }
    })
    const links = graph.links.map((link): KgLink => ({
      source: link.source,
      target: link.target,
      roles: link.roles,
      weight: link.roleWeight,
    }))
    return { nodes, links }
  }, [graph, personNameMode])

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>()
    for (const link of data.links) {
      if (!map.has(link.source)) map.set(link.source, new Set())
      if (!map.has(link.target)) map.set(link.target, new Set())
      map.get(link.source)!.add(link.target)
      map.get(link.target)!.add(link.source)
    }
    return map
  }, [data])

  useEffect(() => {
    fittedRef.current = false
    setHoverKey(null)
  }, [data])

  // Longer links and stronger repulsion than the defaults keep labels apart.
  // Runs once the graph is mounted (it only renders after the first resize).
  const mounted = size.width > 0
  useEffect(() => {
    const fg = graphRef.current
    if (!mounted || !fg) return
    fg.d3Force('charge')?.strength(-140)
    fg.d3Force('link')?.distance(42)
    fg.d3ReheatSimulation()
  }, [data, mounted])

  const inFocus = (key: string) => !hoverKey || key === hoverKey || Boolean(adjacency.get(hoverKey)?.has(key))
  const touchesHover = (link: LinkObject<KgNode, KgLink>) => (
    hoverKey !== null && (endpointKey(link.source) === hoverKey || endpointKey(link.target) === hoverKey)
  )

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden">
      {size.width > 0 && (
        <ForceGraph2D<KgNode, KgLink>
          ref={graphRef}
          width={size.width}
          height={size.height}
          graphData={data}
          nodeId="key"
          backgroundColor="rgba(0,0,0,0)"
          nodeRelSize={3.2}
          cooldownTicks={180}
          onEngineTick={() => {
            for (const node of data.nodes) positionsRef.current.set(node.key, { x: node.x ?? 0, y: node.y ?? 0 })
          }}
          onEngineStop={() => {
            if (fittedRef.current) return
            fittedRef.current = true
            graphRef.current?.zoomToFit(500, 36)
          }}
          linkColor={link => {
            if (!hoverKey) return 'rgba(161,161,170,0.28)'
            return touchesHover(link) ? ACCENT : 'rgba(161,161,170,0.05)'
          }}
          linkWidth={link => (touchesHover(link) ? 1.8 : 0.5 + Math.min(1, link.weight / 50))}
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={(link, ctx, scale) => {
            // The predicate of each hovered triple: the person's roles on that anime.
            if (!touchesHover(link)) return
            const s = link.source as NodeObject<KgNode>
            const t = link.target as NodeObject<KgNode>
            ctx.font = `${10 / scale}px ui-sans-serif, system-ui, sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.lineWidth = 3 / scale
            ctx.strokeStyle = 'rgba(10,10,15,0.9)'
            ctx.fillStyle = ACCENT
            const text = truncate(link.roles.join('·'), 10)
            const mx = ((s.x ?? 0) + (t.x ?? 0)) / 2
            const my = ((s.y ?? 0) + (t.y ?? 0)) / 2
            ctx.strokeText(text, mx, my)
            ctx.fillText(text, mx, my)
          }}
          nodeCanvasObject={(node, ctx, scale) => {
            const x = node.x ?? 0
            const y = node.y ?? 0
            const r = Math.sqrt(node.val) * 3.2
            const focused = node.key === hoverKey
            ctx.globalAlpha = inFocus(node.key) ? 1 : 0.15
            ctx.fillStyle = node.isCenter ? ACCENT : node.kind === 'anime' ? ANIME_COLOR : PERSON_COLOR
            ctx.beginPath()
            if (node.kind === 'anime') ctx.roundRect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8, r * 0.3)
            else ctx.arc(x, y, r, 0, Math.PI * 2)
            ctx.fill()
            if (focused || node.isCenter) {
              ctx.lineWidth = 1.5 / scale
              ctx.strokeStyle = focused ? '#fafafa' : 'rgba(245,199,107,0.5)'
              ctx.stroke()
            }
            // Obsidian-style label density: people always; anime once zoomed in,
            // or when they belong to the hovered neighborhood.
            const hidden = hoverKey
              ? !inFocus(node.key)
              : node.kind === 'anime' && !node.isCenter && scale < 1.6
            if (hidden) {
              ctx.globalAlpha = 1
              return
            }
            const size = (node.isCenter || focused ? 12 : 10) / scale
            ctx.font = `${node.isCenter || focused ? 600 : 400} ${size}px ui-sans-serif, system-ui, sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            ctx.lineWidth = 3 / scale
            ctx.strokeStyle = 'rgba(10,10,15,0.85)'
            ctx.fillStyle = node.isCenter ? '#fde9c3' : node.kind === 'anime' ? '#c5dbe6' : '#e4e4e7'
            const text = focused ? node.label : truncate(node.label, node.kind === 'anime' ? 9 : 8)
            ctx.strokeText(text, x, y + r + 2 / scale)
            ctx.fillText(text, x, y + r + 2 / scale)
            if (focused) {
              ctx.font = `${9.5 / scale}px ui-sans-serif, system-ui, sans-serif`
              ctx.fillStyle = '#a1a1aa'
              ctx.strokeText(node.detail, x, y + r + 2 / scale + size * 1.25)
              ctx.fillText(node.detail, x, y + r + 2 / scale + size * 1.25)
            }
            ctx.globalAlpha = 1
          }}
          onNodeHover={node => {
            setHoverKey(node?.key ?? null)
            onHoverChange?.(node?.key ?? null)
          }}
          onNodeClick={node => {
            if (node.kind === 'person' && !node.isCenter) onSelectPerson(node.id)
          }}
        />
      )}
    </div>
  )
}
