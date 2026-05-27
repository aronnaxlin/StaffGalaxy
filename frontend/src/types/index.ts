export interface GalaxyNode {
  id: string
  name: string
  degree?: number
  x?: number
  y?: number
}

export interface GalaxyEdge {
  source: string
  target: string
  sharedWorksCount: number
}

export interface SearchEntry {
  id: string
  name: string
  degree?: number
}
