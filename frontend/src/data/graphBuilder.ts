import Graph from 'graphology'
import type { LevelData } from './loader'

// Person-galaxy graphs only: the global galaxy renders straight from the
// binary buffers (data/graphBuffers.ts) and never touches graphology.
// graphology remains here because NodePanel neighbor lookups are convenient
// on the small (≤ few hundred node) person graphs.

function sizeFromAttrs(attrs: Record<string, unknown>): number {
  if (attrs.isCenter) return 10
  const dbSize = Number(attrs.nodeSize ?? 0)
  if (dbSize > 0) return Math.max(2.2, dbSize * 0.65)
  const degree = Number(attrs.degree ?? 0)
  return 1.4 + Math.log10(1 + degree) * 1.2
}

function colorFromAttrs(attrs: Record<string, unknown>): string {
  if (attrs.isCenter) return '#fef08a'
  if (attrs.expandedFrom) return '#67e8f9'

  // Obsidian-style: mostly white/gray dots, subtle warmth for high-degree nodes.
  const degree = Number(attrs.degree ?? 0)
  const t = Math.min(1, Math.log10(1 + degree) / 3.5)
  const v = Math.round(195 + t * 60)
  return `rgb(${v},${v},${v})`
}

function edgeStyle(
  sharedWorksCount: number,
  collaborationScore: number | undefined,
  firstYear?: number,
  lastYear?: number,
  expandedFrom?: string,
) {
  const score = collaborationScore ?? sharedWorksCount
  const t = Math.min(1, Math.log10(1 + score) / 2.2)

  return {
    size: 0.2 + t * 0.55,
    color: `rgba(148,163,184,${(0.04 + t * 0.08).toFixed(3)})`,
    sharedWorksCount,
    collaborationScore: score,
    firstYear,
    lastYear,
    expandedFrom,
  }
}

export function buildGraph(data: LevelData): Graph {
  const graph = new Graph({ type: 'undirected', multi: false })
  for (const node of data.nodes) {
    const attrs: Record<string, unknown> = {
      label: node.name,
      x: node.x ?? 0,
      y: node.y ?? 0,
      size: sizeFromAttrs(node as unknown as Record<string, unknown>),
      color: colorFromAttrs(node as unknown as Record<string, unknown>),
      name: node.name,
      nameCn: node.nameCn,
      nameTw: node.nameTw,
      degree: node.degree ?? 0,
      visibleWeightedDegree: node.visibleWeightedDegree,
      roleLayer: node.roleLayer,
      sharedWorksCount: node.sharedWorksCount,
      collaborationScore: node.collaborationScore,
      firstYear: node.firstYear,
      lastYear: node.lastYear,
      neighborRoleTier: node.neighborRoleTier,
      expandedFrom: node.expandedFrom,
    }
    if (node.isCenter) attrs.isCenter = true
    graph.addNode(node.id, attrs)
  }

  for (const edge of data.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      const key = edge.source < edge.target
        ? `${edge.source}|${edge.target}`
        : `${edge.target}|${edge.source}`
      if (!graph.hasEdge(key)) {
        graph.addEdgeWithKey(
          key,
          edge.source,
          edge.target,
          edgeStyle(
            edge.sharedWorksCount,
            edge.collaborationScore,
            edge.firstYear,
            edge.lastYear,
            edge.expandedFrom,
          ),
        )
      }
    }
  }
  return graph
}
