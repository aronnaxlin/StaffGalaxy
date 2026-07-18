import type {
  GalaxyNode,
  GalaxyEdge,
  SearchEntry,
  CollaborationDetail,
  PathResult,
  PersonDetail,
  PersonCreditsResponse,
  Manifest,
} from '../types'
import { recordRuntimeMetric } from './runtimeMetrics'

interface RawEdge { source: string; target: string; w: number; collaborationScore?: number; firstYear?: number; lastYear?: number; selectionReason?: string; expandedFrom?: string }

export type Level = 'person' | 'global'

export interface LevelData {
  nodes: GalaxyNode[]
  edges: GalaxyEdge[]
}

interface PersonGalaxyResponse {
  centerId: string
  nodes: GalaxyNode[]
  edges: RawEdge[]
}

let manifestCache: Manifest | null = null

async function fetchJson<T>(url: string): Promise<T> {
  const startedAt = performance.now()
  const response = await fetch(url)
  const durationMs = Math.round((performance.now() - startedAt) * 10) / 10
  recordRuntimeMetric('api-response', {
    url,
    status: response.status,
    durationMs,
    ok: response.ok,
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${url}`)
  }
  return response.json()
}

export async function loadManifest(): Promise<Manifest> {
  if (manifestCache) return manifestCache
  manifestCache = await fetchJson<Manifest>('/api/manifest')
  return manifestCache
}

export async function loadSearchIndex(): Promise<SearchEntry[]> {
  return fetchJson<SearchEntry[]>('/api/search/persons?limit=50000')
}

export async function searchPersons(query: string): Promise<SearchEntry[]> {
  return fetchJson<SearchEntry[]>(`/api/search/persons?q=${encodeURIComponent(query)}&limit=8`)
}

export async function loadPersonSearchEntry(personId: string): Promise<SearchEntry | null> {
  const results = await fetchJson<SearchEntry[]>(`/api/search/persons?q=${encodeURIComponent(personId)}&limit=1`)
  return results[0] ?? null
}

const personGalaxyCache = new Map<string, LevelData>()

export async function loadPersonGalaxy(
  personId: string,
  options: { limit?: number; minShared?: number } = {},
): Promise<LevelData> {
  const limit = options.limit ?? 220
  const minShared = options.minShared ?? 1
  const cacheKey = `${personId}|${limit}|${minShared}`
  const cached = personGalaxyCache.get(cacheKey)
  if (cached) return cached

  const data = await fetchJson<PersonGalaxyResponse>(
    `/api/person/${personId}/galaxy?limit=${limit}&min_shared=${minShared}`,
  )
  const levelData: LevelData = {
    nodes: data.nodes,
    edges: data.edges.map(e => ({
      source: e.source,
      target: e.target,
      sharedWorksCount: e.w,
      collaborationScore: e.collaborationScore,
      firstYear: e.firstYear,
      lastYear: e.lastYear,
      selectionReason: e.selectionReason,
      expandedFrom: e.expandedFrom,
    })),
  }
  personGalaxyCache.set(cacheKey, levelData)
  return levelData
}

const personDetailCache = new Map<string, PersonDetail>()

export async function loadPersonDetail(personId: string): Promise<PersonDetail> {
  const cached = personDetailCache.get(personId)
  if (cached) return cached

  const data = await fetchJson<PersonDetail>(`/api/person/${personId}/detail`)
  personDetailCache.set(personId, data)
  return data
}

const personCreditsCache = new Map<string, PersonCreditsResponse>()

export async function loadPersonCredits(personId: string): Promise<PersonCreditsResponse> {
  const cached = personCreditsCache.get(personId)
  if (cached) return cached

  const data = await fetchJson<PersonCreditsResponse>(`/api/person/${personId}/credits?limit=2000`)
  personCreditsCache.set(personId, data)
  return data
}

export async function loadShortestPath(personA: string, personB: string): Promise<PathResult> {
  return fetchJson<PathResult>(`/api/path/${personA}/${personB}`)
}

const collabCache = new Map<string, CollaborationDetail>()

function orientCollaborationDetail(
  detail: CollaborationDetail,
  personA: string,
  personB: string,
): CollaborationDetail {
  if (detail.personA.id === personA && detail.personB.id === personB) {
    return detail
  }
  if (detail.personA.id !== personB || detail.personB.id !== personA) {
    return detail
  }

  return {
    ...detail,
    personA: detail.personB,
    personB: detail.personA,
    sharedWorks: detail.sharedWorks.map(work => ({
      ...work,
      personARoles: work.personBRoles,
      personBRoles: work.personARoles,
    })),
  }
}

export async function loadCollaborationDetail(personA: string, personB: string): Promise<CollaborationDetail> {
  const key = personA < personB ? `${personA}|${personB}` : `${personB}|${personA}`
  const cached = collabCache.get(key)
  if (cached) return orientCollaborationDetail(cached, personA, personB)

  const data = await fetchJson<CollaborationDetail>(`/api/collaboration/${personA}/${personB}`)
  collabCache.set(key, data)
  return orientCollaborationDetail(data, personA, personB)
}
