import Graph from 'graphology'
import type { Level } from './loader'
import type { LevelData } from './loader'

function sizeFromAttrs(attrs: Record<string, unknown>, level: Level): number {
  if (attrs.isCenter) return 10
  const dbSize = Number(attrs.nodeSize ?? 0)
  const degree = Number(attrs.degree ?? 0)
  if (dbSize > 0) {
    return level === 'person' ? Math.max(2.2, dbSize * 0.65) : Math.max(1.8, dbSize * 0.55)
  }
  return 1.4 + Math.log10(1 + degree) * 1.2
}

function colorFromAttrs(attrs: Record<string, unknown>): string {
  if (attrs.isCenter) return '#fef08a'

  const roleLayer = attrs.roleLayer as string | undefined
  const degree = Number(attrs.degree ?? 0)
  // Obsidian-style: mostly white/gray dots, subtle warmth for high-degree nodes.
  const t = Math.min(1, Math.log10(1 + degree) / 3.5)

  if (roleLayer === 'Tier A') {
    const v = Math.round(210 + t * 45)
    return `rgb(${v},${Math.round(v * 0.94)},${Math.round(v * 0.88)})`
  }
  const v = Math.round(195 + t * 60)
  return `rgb(${v},${v},${v})`
}

function edgeStyle(sharedWorksCount: number, collaborationScore: number | undefined, level: Level) {
  const score = collaborationScore ?? sharedWorksCount
  const t = Math.min(1, Math.log10(1 + score) / 2.2)

  const alpha = level === 'l1'
    ? 0.006 + t * 0.024
    : level === 'person'
      ? 0.04 + t * 0.08
      : 0.01 + t * 0.04

  const size = level === 'l1'
    ? 0.1 + t * 0.3
    : level === 'person'
      ? 0.2 + t * 0.55
      : 0.14 + t * 0.44

  return {
    size,
    color: `rgba(148,163,184,${alpha.toFixed(3)})`,
    sharedWorksCount,
    collaborationScore: score,
  }
}

function addLevelData(graph: Graph, data: LevelData, level: Level): void {
  for (const node of data.nodes) {
    const attrs: Record<string, unknown> = {
      label: node.name,
      x: node.x ?? 0,
      y: node.y ?? 0,
      size: sizeFromAttrs(node as unknown as Record<string, unknown>, level),
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
          edgeStyle(edge.sharedWorksCount, edge.collaborationScore, level),
        )
      }
    }
  }
}

export function buildGraph(data: LevelData, level: Level = 'l0'): Graph {
  const graph = new Graph({ type: 'undirected', multi: false })
  addLevelData(graph, data, level)
  return graph
}
