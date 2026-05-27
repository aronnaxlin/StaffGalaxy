import Graph from 'graphology'
import type { Level } from './loader'
import type { LevelData } from './loader'

function sizeFromDegree(degree: number): number {
  return 1.5 + Math.log10(1 + degree) * 1.8
}

function colorFromDegree(degree: number): string {
  const t = Math.min(1, Math.log10(1 + degree) / 3)
  const v = Math.round(110 + t * 145)
  return `rgb(${v},${v},${v + 8})`
}

function edgeStyle(sharedWorksCount: number, level: Level) {
  const t = Math.min(1, Math.log10(1 + sharedWorksCount) / 2)
  const alpha = level === 'l1'
    ? 0.008 + t * 0.028
    : 0.012 + t * 0.045
  const size = level === 'l1'
    ? 0.12 + t * 0.32
    : 0.16 + t * 0.46

  return {
    size,
    color: `rgba(148,163,184,${alpha.toFixed(3)})`,
    sharedWorksCount,
  }
}

function addLevelData(graph: Graph, data: LevelData, level: Level): void {
  for (const node of data.nodes) {
    const degree = node.degree ?? 0
    graph.addNode(node.id, {
      label: node.name,
      x: node.x ?? 0,
      y: node.y ?? 0,
      size: sizeFromDegree(degree),
      color: colorFromDegree(degree),
      name: node.name,
      degree,
    })
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
          edgeStyle(edge.sharedWorksCount, level),
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

// In-place swap to avoid re-mounting SigmaContainer
export function swapGraph(graph: Graph, data: LevelData, level: Level): void {
  graph.clear()
  addLevelData(graph, data, level)
}
