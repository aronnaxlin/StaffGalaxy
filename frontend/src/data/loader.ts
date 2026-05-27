import type { GalaxyNode, GalaxyEdge, SearchEntry } from '../types'

interface RawEdge { source: string; target: string; w: number }

export type Level = 'global' | 'l0' | 'l1'

export interface LevelData {
  nodes: GalaxyNode[]
  edges: GalaxyEdge[]
}

const cache: Partial<Record<Level, LevelData>> = {}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${url}`)
  }
  return response.json()
}

export async function loadLevel(level: Level): Promise<LevelData> {
  if (cache[level]) return cache[level]!
  const [nodes, rawEdges] = await Promise.all([
    fetchJson<GalaxyNode[]>(`/api/graph/${level}/nodes`),
    fetchJson<RawEdge[]>(`/api/graph/${level}/edges`),
  ])
  const edges: GalaxyEdge[] = rawEdges.map(e => ({
    source: e.source,
    target: e.target,
    sharedWorksCount: e.w,
  }))
  cache[level] = { nodes, edges }
  return cache[level]!
}

export async function loadSearchIndex(): Promise<SearchEntry[]> {
  return fetchJson<SearchEntry[]>('/api/search/persons')
}
