import type { GalaxyNode, GalaxyEdge, SearchEntry } from '../types'

interface RawEdge { source: string; target: string; w: number }

export type Level = 'l0' | 'l1'

export interface LevelData {
  nodes: GalaxyNode[]
  edges: GalaxyEdge[]
}

const cache: Partial<Record<Level, LevelData>> = {}

export async function loadLevel(level: Level): Promise<LevelData> {
  if (cache[level]) return cache[level]!
  const [nodesRes, edgesRes] = await Promise.all([
    fetch(`/data/galaxy/nodes-${level}.json`),
    fetch(`/data/galaxy/edges-${level}.json`),
  ])
  const nodes: GalaxyNode[] = await nodesRes.json()
  const rawEdges: RawEdge[] = await edgesRes.json()
  const edges: GalaxyEdge[] = rawEdges.map(e => ({
    source: e.source,
    target: e.target,
    sharedWorksCount: e.w,
  }))
  cache[level] = { nodes, edges }
  return cache[level]!
}

export async function loadSearchIndex(): Promise<SearchEntry[]> {
  const res = await fetch('/data/search/persons-index.json')
  return res.json()
}
