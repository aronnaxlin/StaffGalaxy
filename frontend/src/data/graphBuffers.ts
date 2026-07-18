import type { Manifest } from '../types'
import { recordRuntimeMetric } from './runtimeMetrics'

// Binary graph transport (edge-rendering plan Phase 2). Mirrors
// staff_galaxy/graph_buffers.py — keep the segment order in sync.
const SEGMENT_NAMES = [
  'positions',
  'sizes',
  'colors',
  'community',
  'edgePairs',
  'edgeWeights',
  'edgeShared',
] as const

const MAGIC = 0x31584753 // "SGX1" little-endian
const HEADER_SIZE = 16 + SEGMENT_NAMES.length * 8

export const NO_COMMUNITY = 0xffff

export interface GraphNodeMeta {
  id: string
  name: string
  nameCn?: string
  nameTw?: string
  degree: number
  weightedDegree: number
}

export interface GraphMetaResponse {
  nodeCount: number
  edgeCount: number
  layoutMethod: string
  nodes: GraphNodeMeta[]
}

export interface GlobalGraphData {
  nodeCount: number
  edgeCount: number
  layoutMethod: string
  positions: Float32Array
  sizes: Float32Array
  colors: Uint8Array
  community: Uint16Array
  edgePairs: Uint32Array
  edgeWeights: Float32Array
  edgeShared: Uint16Array
  meta: GraphNodeMeta[]
  nodeIndexById: Map<string, number>
}

function parseGraphBuffers(buffer: ArrayBuffer): Omit<GlobalGraphData, 'meta' | 'nodeIndexById' | 'layoutMethod'> {
  const view = new DataView(buffer)
  if (view.getUint32(0, true) !== MAGIC) {
    throw new Error('Bad graph buffers magic')
  }
  // Version 2 = segment offsets 4-byte aligned (v1 packed back-to-back and
  // Float32Array/Uint32Array views threw on the misaligned edge segments).
  const version = view.getUint32(4, true)
  if (version !== 2) {
    throw new Error(`Unsupported graph buffers version: ${version}`)
  }
  const nodeCount = view.getUint32(8, true)
  const edgeCount = view.getUint32(12, true)

  const segments: Record<string, { offset: number; count: number }> = {}
  SEGMENT_NAMES.forEach((name, i) => {
    segments[name] = {
      offset: view.getUint32(16 + i * 8, true),
      count: view.getUint32(16 + i * 8 + 4, true),
    }
  })
  const { positions, sizes, colors, community, edgePairs, edgeWeights, edgeShared } = segments

  const misaligned = [positions, sizes, edgePairs, edgeWeights].some(s => s.offset % 4 !== 0)
    || community.offset % 2 !== 0
    || edgeShared.offset % 2 !== 0
  if (
    positions.count !== nodeCount * 2
    || sizes.count !== nodeCount
    || colors.count !== nodeCount * 4
    || community.count !== nodeCount
    || edgePairs.count !== edgeCount * 2
    || edgeWeights.count !== edgeCount
    || edgeShared.count !== edgeCount
    || buffer.byteLength < HEADER_SIZE
    || misaligned
  ) {
    throw new Error('Graph buffers payload malformed')
  }

  return {
    nodeCount,
    edgeCount,
    positions: new Float32Array(buffer, positions.offset, positions.count),
    sizes: new Float32Array(buffer, sizes.offset, sizes.count),
    colors: new Uint8Array(buffer, colors.offset, colors.count),
    community: new Uint16Array(buffer, community.offset, community.count),
    edgePairs: new Uint32Array(buffer, edgePairs.offset, edgePairs.count),
    edgeWeights: new Float32Array(buffer, edgeWeights.offset, edgeWeights.count),
    edgeShared: new Uint16Array(buffer, edgeShared.offset, edgeShared.count),
  }
}

let cache: Promise<GlobalGraphData> | null = null

// Both URLs carry ?v=<archive name> so the server's immutable Cache-Control is
// safe: a new Archive snapshot is a new URL.
export function loadGlobalGraph(manifest: Manifest): Promise<GlobalGraphData> {
  if (cache) return cache

  // archiveName covers snapshot swaps; geometryFingerprint covers in-place
  // layout migrations — both bust the server's immutable cache entry.
  const tag = encodeURIComponent(
    `${manifest.snapshot?.archiveName ?? 'unknown'}|${manifest.graph.geometryFingerprint}`,
  )
  cache = (async () => {
    const startedAt = performance.now()
    const [buffersResponse, metaResponse] = await Promise.all([
      fetch(`/api/graph/buffers?v=${tag}`),
      fetch(`/api/graph/meta?v=${tag}`),
    ])
    if (!buffersResponse.ok) throw new Error(`Buffers request failed: ${buffersResponse.status}`)
    if (!metaResponse.ok) throw new Error(`Meta request failed: ${metaResponse.status}`)

    const [buffer, metaJson] = await Promise.all([
      buffersResponse.arrayBuffer(),
      metaResponse.json() as Promise<GraphMetaResponse>,
    ])
    const parsed = parseGraphBuffers(buffer)
    if (metaJson.nodeCount !== parsed.nodeCount || metaJson.edgeCount !== parsed.edgeCount) {
      throw new Error('Graph buffers/meta count mismatch')
    }
    const nodeIndexById = new Map<string, number>()
    metaJson.nodes.forEach((node, index) => nodeIndexById.set(node.id, index))

    const durationMs = Math.round((performance.now() - startedAt) * 10) / 10
    recordRuntimeMetric('graph-buffers-loaded', {
      bytes: buffer.byteLength,
      nodes: parsed.nodeCount,
      edges: parsed.edgeCount,
      durationMs,
    })

    return {
      ...parsed,
      layoutMethod: metaJson.layoutMethod,
      meta: metaJson.nodes,
      nodeIndexById,
    }
  })()
  cache.catch(() => {
    cache = null
  })
  return cache
}
