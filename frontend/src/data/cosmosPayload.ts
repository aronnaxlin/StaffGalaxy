import { NO_COMMUNITY, type GlobalGraphData } from './graphBuffers'
import { displayPersonName } from './personNames'
import type { PersonNameMode } from '../types'

export const COSMOS_SPACE_SIZE = 8192
export const COSMOS_LAYOUT_SIZE = 4300

export interface CosmosPayload {
  nodeIds: string[]
  nodeIndexById: Map<string, number>
  positions: Float32Array
  pointColors: Float32Array
  pointSizes: Float32Array
  degrees: Uint32Array
  // Edges sorted descending by strength (sharedWorksCount, then collaborationScore)
  // — the server ships them pre-sorted in the binary buffers, so any zoom-dependent
  // edge budget is a zero-copy prefix `.subarray()`: no per-frame filter/rebuild.
  sortedLinks: Float32Array
  sortedLinkColors: Float32Array
  sortedLinkWidths: Float32Array
  sortedSharedCounts: Int32Array | Uint16Array
  totalEdgeCount: number
  // Point index -> indices into the sorted edge arrays incident to that point.
  // Built once so hover highlighting is O(degree): cosmos.gl's own
  // getConnectedLinkIndices(pointIndices) requires BOTH endpoints of a link to
  // be in the given set ("edges within a selection"), which returns nothing
  // useful for a single hovered point — this is our own incident-edge index.
  pointToLinkIndices: number[][]
  nodeLabels: Map<string, string>
}

function hslToRgbNormalized(h: number, s: number, l: number): [number, number, number] {
  const c = (1 - Math.abs(2 * l - 1)) * s
  const hp = (((h % 360) + 360) % 360) / 60
  const x = c * (1 - Math.abs((hp % 2) - 1))
  let rgb: [number, number, number]
  if (hp < 1) rgb = [c, x, 0]
  else if (hp < 2) rgb = [x, c, 0]
  else if (hp < 3) rgb = [0, c, x]
  else if (hp < 4) rgb = [0, x, c]
  else if (hp < 5) rgb = [x, 0, c]
  else rgb = [c, 0, x]
  const m = l - c / 2
  return [rgb[0] + m, rgb[1] + m, rgb[2] + m]
}

// Community hue shift (plan Phase 3.3): low-saturation golden-angle hue per
// Leiden community over the server's neutral gray base — Obsidian group colors.
// cosmos.gl v3 color buffers are RGBA normalized to [0, 1] (v2 used RGB 0-255).
function communityColor(baseValue: number, communityId: number): [number, number, number, number] {
  if (communityId === NO_COMMUNITY) {
    const v = baseValue / 255
    return [v, v, v, 1]
  }
  const hue = (communityId * 137.508) % 360
  const lightness = 0.45 + (baseValue / 255) * 0.35
  const [r, g, b] = hslToRgbNormalized(hue, 0.32, lightness)
  return [r, g, b, 1]
}

function buildEdgeStyleArrays(
  totalEdgeCount: number,
  scoreAt: (index: number) => number,
): { colors: Float32Array; widths: Float32Array } {
  const colors = new Float32Array(totalEdgeCount * 4)
  const widths = new Float32Array(totalEdgeCount)
  for (let index = 0; index < totalEdgeCount; index += 1) {
    const score = scoreAt(index)
    const t = Math.min(1, Math.log10(1 + (score > 0 ? score : 1)) / 2.2)

    const r = 130 + t * 80
    const g = 148 + t * 65
    const b = 175 + t * 55
    const alpha = 10 + t * 22

    colors[index * 4] = r / 255
    colors[index * 4 + 1] = g / 255
    colors[index * 4 + 2] = b / 255
    colors[index * 4 + 3] = alpha / 255

    widths[index] = 0.14 + t * 0.44
  }
  return { colors, widths }
}

function buildIncidence(nodeCount: number, links: ArrayLike<number>, edgeCount: number): number[][] {
  const pointToLinkIndices: number[][] = Array.from({ length: nodeCount }, () => [])
  for (let index = 0; index < edgeCount; index += 1) {
    pointToLinkIndices[links[index * 2]].push(index)
    pointToLinkIndices[links[index * 2 + 1]].push(index)
  }
  return pointToLinkIndices
}

// Global galaxy: typed arrays straight from the binary buffers — no graphology,
// no JSON row mapping, no re-normalization (the server ships Cosmos-space coords).
export function buildGlobalPayload(data: GlobalGraphData, personNameMode: PersonNameMode): CosmosPayload {
  const { nodeCount, edgeCount } = data
  const nodeIds = data.meta.map(node => node.id)

  const pointColors = new Float32Array(nodeCount * 4)
  const degrees = new Uint32Array(nodeCount)
  const nodeLabels = new Map<string, string>()
  for (let index = 0; index < nodeCount; index += 1) {
    const [r, g, b, a] = communityColor(data.colors[index * 4], data.community[index])
    pointColors[index * 4] = r
    pointColors[index * 4 + 1] = g
    pointColors[index * 4 + 2] = b
    pointColors[index * 4 + 3] = a

    const meta = data.meta[index]
    degrees[index] = meta.degree
    nodeLabels.set(meta.id, displayPersonName(meta, personNameMode))
  }

  // cosmos.gl v3 setLinks wants Float32; the buffer ships u32 node indices.
  const sortedLinks = new Float32Array(data.edgePairs)
  const { colors: sortedLinkColors, widths: sortedLinkWidths } = buildEdgeStyleArrays(
    edgeCount,
    index => data.edgeWeights[index] > 0 ? data.edgeWeights[index] : data.edgeShared[index],
  )

  return {
    nodeIds,
    nodeIndexById: data.nodeIndexById,
    positions: data.positions,
    pointColors,
    pointSizes: data.sizes,
    degrees,
    sortedLinks,
    sortedLinkColors,
    sortedLinkWidths,
    sortedSharedCounts: data.edgeShared,
    totalEdgeCount: edgeCount,
    pointToLinkIndices: buildIncidence(nodeCount, data.edgePairs, edgeCount),
    nodeLabels,
  }
}
