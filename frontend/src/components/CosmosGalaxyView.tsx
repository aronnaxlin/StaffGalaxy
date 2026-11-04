import { useCallback, useEffect, useRef, useState } from 'react'
import { Graph as CosmosGraph } from '@cosmos.gl/graph'
import { Popover, Slider } from 'radix-ui'
import { Settings2 } from 'lucide-react'
import type { CosmosPayload } from '../data/cosmosPayload'
import { COSMOS_SPACE_SIZE } from '../data/cosmosPayload'
import { loadCommunityLabels, loadFeaturedPeople } from '../data/loader'
import { displaySubjectName } from '../data/personNames'
import { recordRuntimeMetric } from '../data/runtimeMetrics'
import type { CommunityLabel, PersonNameMode } from '../types'
import { iconButton, panelShell } from './ui'

interface CosmosGalaxyViewProps {
  payload: CosmosPayload
  selectedNode: string | null
  personNameMode: PersonNameMode
  onNodeClick: (nodeId: string) => void
  onBackgroundClick: () => void
}

interface GraphLabel {
  id: string
  label: string
  x: number
  y: number
  center: boolean
}

interface CommunityTag {
  id: string
  level: 0 | 1
  title: string
  subtitle: string
  x: number
  y: number
}

interface AvatarSpot {
  id: string
  x: number
  y: number
  size: number
}

// A community drawn at least this many pixels across (75th-percentile radius)
// is labelled by its sub-communities instead; below MIN it gets no label.
const COMMUNITY_SPLIT_PX = 220
const COMMUNITY_MIN_PX = 28
// Sub-communities spread over most of their parent have no spot to label.
const SUB_COMMUNITY_MAX_SPREAD = 0.6

// Only featured people get avatars (/api/graph/featured: the strongest and the
// most discussed on Bangumi), and only those on screen load. They replace dots
// where they do not overlap, in list order, so zooming in reveals more of them.
// Pixels at the opening view. Zooming in, avatars grow like the dots
// (zoom^POINT_ZOOM_GROWTH); zooming out, they shrink with the view.
const AVATAR_SIZE = 24
const AVATAR_MIN_SIZE = 16
const AVATAR_MAX_SIZE = 44
// Bangumi redirects to the image (cached a day); people without one get a
// 500×500 placeholder, while real grid avatars are 75×75.
const AVATAR_PLACEHOLDER_MIN_WIDTH = 100
const HEADER_HEIGHT = 76

// The opening view frames the dense core, not the whole space: isolates sit on
// an outer ring and small communities drift to the rim, and fitting all of
// them leaves the galaxy a small disc in the middle of the screen.
const CORE_DISTANCE_QUANTILE = 0.8
const CORE_FIT_PADDING = 0.04

// Flat [x0, y0, ...] for fitViewByPointPositions: unlike fitViewByPointIndices
// it needs no GPU read-back, which is not ready yet on first load.
function corePositions(payload: CosmosPayload): number[] {
  return coreIndices(payload).flatMap(i => [payload.positions[i * 2], payload.positions[i * 2 + 1]])
}

function coreIndices(payload: CosmosPayload): number[] {
  const connected: number[] = []
  for (let i = 0; i < payload.degrees.length; i += 1) {
    if (payload.degrees[i] > 0) connected.push(i)
  }
  const quantile = (values: number[], q: number) =>
    values.sort((a, b) => a - b)[Math.min(values.length - 1, Math.floor(values.length * q))] ?? 0
  const cx = quantile(connected.map(i => payload.positions[i * 2]), 0.5)
  const cy = quantile(connected.map(i => payload.positions[i * 2 + 1]), 0.5)
  const distance = (i: number) => Math.hypot(payload.positions[i * 2] - cx, payload.positions[i * 2 + 1] - cy)
  const cutoff = quantile(connected.map(distance), CORE_DISTANCE_QUANTILE)
  return connected.filter(i => distance(i) <= cutoff)
}

function avatarUrl(personId: string): string {
  return `https://api.bgm.tv/v0/persons/${personId}/image?type=grid`
}

// Hidden until loaded so a slow network shows the plain dot, then fades in.
function Avatar({ spot, onMissing }: { spot: AvatarSpot; onMissing: (id: string) => void }) {
  const [loaded, setLoaded] = useState(false)
  return (
    <img
      src={avatarUrl(spot.id)}
      alt=""
      decoding="async"
      draggable={false}
      onLoad={event => {
        if (event.currentTarget.naturalWidth > AVATAR_PLACEHOLDER_MIN_WIDTH) onMissing(spot.id)
        else setLoaded(true)
      }}
      onError={() => onMissing(spot.id)}
      className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full object-cover ring-1 ring-white/30 transition-opacity duration-300 ${
        loaded ? 'opacity-100' : 'opacity-0'
      }`}
      style={{ left: spot.x, top: spot.y, width: spot.size, height: spot.size }}
    />
  )
}

// Edge count to keep on screen at the current zoom level, taken as a prefix of the
// strength-sorted edge arrays and scaled by the render-quality level. Only the
// prefix is uploaded: cosmos.gl pads every link by a 0.5 px smoothing band, so a
// zero-width link is still rasterized along its whole length (measured: 20K
// visible of 107K uploaded cost the same as all 107K). Re-uploading a prefix
// takes ~10-20 ms even under software rendering.
function edgeBudgetForZoom(zoom: number): number {
  if (zoom > 1.1) return 30_000
  if (zoom > 0.75) return 50_000
  return 80_000
}

// Adaptive render quality (dynamic resolution): step down when frames are slow,
// back up only after sustained headroom. Pixel ratio goes first, edges after.
const QUALITY_LEVELS = [
  { pixelRatio: 2, edgeScale: 1 },
  { pixelRatio: 1.5, edgeScale: 1 },
  { pixelRatio: 1, edgeScale: 0.6 },
  { pixelRatio: 1, edgeScale: 0.3 },
  { pixelRatio: 1, edgeScale: 0.12 },
  { pixelRatio: 1, edgeScale: 0.05 },
] as const
const QUALITY_STORAGE_KEY = 'staffGalaxy.renderQuality'
const SLOW_FRAME_MS = 26 // median frame time above this (~38 fps) steps quality down
const FAST_FRAME_MS = 17.5 // ...below this for UPGRADE_WINDOWS windows steps it up
const UPGRADE_WINDOWS = 6

function initialQualityLevel(): number {
  try {
    const raw = window.localStorage.getItem(QUALITY_STORAGE_KEY)
    const stored = raw === null ? NaN : Number(raw) // Number(null) would read as level 0
    if (Number.isInteger(stored) && stored >= 0 && stored < QUALITY_LEVELS.length) return stored
  } catch {
    // Storage unavailable (private mode): fall through to detection.
  }
  // Software rasterizers start at the floor instead of crawling down to it.
  const gl = document.createElement('canvas').getContext('webgl2')
  const info = gl?.getExtension('WEBGL_debug_renderer_info')
  const renderer = info ? String(gl!.getParameter(info.UNMASKED_RENDERER_WEBGL)) : ''
  // Release the probe context now: browsers cap live WebGL contexts and evict
  // the oldest one, which would be the galaxy's own.
  gl?.getExtension('WEBGL_lose_context')?.loseContext()
  return /swiftshader|llvmpipe|software/i.test(renderer) ? QUALITY_LEVELS.length - 1 : 0
}

const FOCUS_LABEL_LIMIT = 14
const FOCUS_CAMERA_MS = 650
const FOCUS_ZOOM = 2.4
// Base edge colors are deliberately faint (alpha ~0.04-0.13); the selected
// person's edges are repainted in this warm tone so their circle reads at a glance.
const FOCUS_EDGE_RGBA = [245 / 255, 199 / 255, 107 / 255, 0.55] as const
// cosmos.gl redraws every animation frame forever; on a fanless laptop that keeps
// the GPU busy even when nothing moves. Rendering pauses after this much quiet.
const IDLE_PAUSE_MS = 1500

// cosmos.gl draws points at size × zoom, so zooming in 4× made every dot 4×
// larger and clusters stayed solid. Past the opening view, dots grow with
// zoom^POINT_ZOOM_GROWTH instead (4× zoom → 2× dots), letting clusters open up.
const POINT_SIZE_SCALE = 0.65
const POINT_ZOOM_GROWTH = 0.5

const COSMOS_CONFIG = {
  backgroundColor: '#0b0c10',
  enableSimulation: false,
  // Keep v2's instant-snap updates; v3 defaults to 800ms animated transitions on
  // position/color/size/width changes, which would visibly lag every LOD/hover step.
  transitionDuration: 0,
  spaceSize: COSMOS_SPACE_SIZE,
  rescalePositions: false,
  // The initial view is set by this component (fit, or glide to a deep-linked
  // person); cosmos.gl's own delayed fit would override that camera move.
  fitViewOnInit: false,
  hoveredPointCursor: 'pointer',
  renderHoveredPointRing: true,
  hoveredPointRingColor: '#fafafa',
  focusedPointRingColor: '#f5c76b',
  pointDefaultColor: '#cbd5e1',
  pointGreyoutOpacity: 0.06,
  // Slightly translucent and smaller, so dense clusters show depth where
  // points overlap instead of filling into solid discs.
  pointOpacity: 0.78,
  pointSizeScale: POINT_SIZE_SCALE,
  linkDefaultColor: [148 / 255, 163 / 255, 184 / 255, 0.1] as [number, number, number, number],
  linkOpacity: 1,
  linkVisibilityDistanceRange: [35, 180],
  linkVisibilityMinTransparency: 0.02,
  scalePointsOnZoom: true,
  scaleLinksOnZoom: false,
  attribution: '',
}

const MIN_EDGE_BUDGET = 20_000

// Settings slider position (1–100) → edge budget, log-spaced up to every edge.
function edgeBudgetForSlider(slider: number, totalEdges: number): number {
  const t = (slider - 1) / 99
  return Math.round(Math.exp(Math.log(MIN_EDGE_BUDGET) + t * (Math.log(totalEdges) - Math.log(MIN_EDGE_BUDGET))))
}

const sliderRoot = 'relative flex h-4 w-full touch-none select-none items-center'
const sliderTrack = 'relative h-1 grow rounded bg-white/10'
const sliderRange = 'absolute h-full rounded bg-[#f5c76b]'
const sliderThumb = 'block h-3.5 w-3.5 rounded-full bg-zinc-100 shadow focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#f5c76b]'

// startFrames/stopFrames are TypeScript-private in cosmos.gl but are the only way
// to pause its render loop. Feature-detected: if a release drops them, rendering
// simply stays continuous (the previous behavior). requestAnimationFrameId is 0
// while paused; startFrames must only run then — hover callbacks fire inside a
// frame, and restarting there would fork a second render loop.
type FrameControl = { startFrames?: () => void; stopFrames?: () => void; requestAnimationFrameId?: number }

export function CosmosGalaxyView({
  payload,
  selectedNode,
  personNameMode,
  onNodeClick,
  onBackgroundClick,
}: CosmosGalaxyViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cosmosRef = useRef<CosmosGraph | null>(null)
  const payloadRef = useRef<CosmosPayload | null>(null)
  const selectedNodeRef = useRef<string | null>(selectedNode)
  const edgeCountRef = useRef(0)
  // What is uploaded: the first `prefix` sorted links, then `extras` (the selected
  // person's links beyond the prefix). Highlight indices refer to this order.
  const uploadedRef = useRef<{ prefix: number; extras: Map<number, number>; key: string }>({
    prefix: 0, extras: new Map(), key: '',
  })
  // Lazy initializer: runs once. (useRef(initialQualityLevel()) would re-run the
  // WebGL probe on every render.)
  const [initialQuality] = useState(initialQualityLevel)
  const qualityRef = useRef(initialQuality)
  // Lowest level index that proved too slow this session; never upgrade back into it.
  const qualityFloorRef = useRef(0)
  const labelIndicesRef = useRef<number[]>([])
  const idleTimerRef = useRef(0)
  const applyEdgeDensityRef = useRef<(() => void) | null>(null)
  const hoverLabelRef = useRef<HTMLDivElement | null>(null)
  const hoveredNodeRef = useRef<string | null>(null)
  const lastPointerPositionRef = useRef<[number, number] | null>(null)
  const highlightedPointerPositionRef = useRef<[number, number] | null>(null)
  const minDegreeRef = useRef(0)
  const edgeBudgetOverrideRef = useRef(0)
  // Callbacks live in refs so a parent re-render never recreates the WebGL graph.
  const onNodeClickRef = useRef(onNodeClick)
  const onBackgroundClickRef = useRef(onBackgroundClick)
  const [visibleEdgeCount, setVisibleEdgeCount] = useState(0)
  const [edgeCutoff, setEdgeCutoff] = useState(0)
  const [labels, setLabels] = useState<GraphLabel[]>([])
  const communitiesRef = useRef<CommunityLabel[]>([])
  const featuredRef = useRef<string[]>([])
  const nameModeRef = useRef(personNameMode)
  // Zoom level of the opening view; point growth is damped beyond it. cosmos.gl
  // may defer the opening fit until its WebGL device is ready, so the level is
  // captured from the first zoom event after the fit, not read right after it.
  const zoomRefRef = useRef<number | null>(null)
  const awaitingReferenceRef = useRef(false)
  const pendingFocusRef = useRef(false)
  const focusSelectionRef = useRef<((animate: boolean) => void) | null>(null)
  // Avatars that failed or turned out to be Bangumi's placeholder this session.
  const missingAvatarsRef = useRef(new Set<string>())
  const [communityTags, setCommunityTags] = useState<CommunityTag[]>([])
  const [avatars, setAvatars] = useState<AvatarSpot[]>([])
  // Avatars are far larger than their dots, so clicks and hovers inside one go
  // to its person instead of whichever dot cosmos.gl finds nearest.
  const avatarsRef = useRef<AvatarSpot[]>([])
  const avatarHoverRef = useRef<string | null>(null)
  const [minDegree, setMinDegree] = useState(0)
  const [edgeBudgetSlider, setEdgeBudgetSlider] = useState(0)
  const [qualityLevel, setQualityLevel] = useState(initialQuality)

  // Resume rendering and re-arm the idle pause. Call after anything that changes
  // what is on screen (config, data, camera) and on every pointer/wheel input.
  const wake = useCallback((busyMs = 0) => {
    const frames = cosmosRef.current as unknown as FrameControl | null
    if (!frames?.startFrames || !frames.stopFrames) return
    window.clearTimeout(idleTimerRef.current)
    if (!frames.requestAnimationFrameId) frames.startFrames()
    idleTimerRef.current = window.setTimeout(() => frames.stopFrames?.(), busyMs + IDLE_PAUSE_MS)
  }, [])

  // Links incident to a point, strongest first (incidence lists are in sorted order).
  const egoLinks = useCallback((index: number) => payloadRef.current?.pointToLinkIndices[index] ?? [], [])

  const otherEnd = useCallback((linkIndex: number, index: number) => {
    const links = payloadRef.current!.sortedLinks
    const source = links[linkIndex * 2]
    return source === index ? links[linkIndex * 2 + 1] : source
  }, [])

  const uploadedIndex = useCallback((linkIndex: number) => {
    const { prefix, extras } = uploadedRef.current
    return linkIndex < prefix ? linkIndex : extras.get(linkIndex) ?? -1
  }, [])

  const applyEdgeDensity = useCallback((force = false) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return

    const budget = edgeBudgetOverrideRef.current > 0
      ? edgeBudgetOverrideRef.current
      : Math.round(edgeBudgetForZoom(cosmos.getZoomLevel()) * QUALITY_LEVELS[qualityRef.current].edgeScale)
    const n = Math.min(budget, payload.totalEdgeCount)
    const selectedIndex = selectedNodeRef.current ? payload.nodeIndexById.get(selectedNodeRef.current) : undefined
    const key = `${n}|${selectedIndex ?? ''}`
    if (!force && key === uploadedRef.current.key) return

    // The selected person's edges are always drawn, whatever the budget.
    const ego = selectedIndex !== undefined ? payload.pointToLinkIndices[selectedIndex] : []
    const extraLinks = ego.filter(li => li >= n)
    const total = n + extraLinks.length
    const links = new Float32Array(total * 2)
    const colors = new Float32Array(total * 4)
    const widths = new Float32Array(total)
    links.set(payload.sortedLinks.subarray(0, n * 2))
    colors.set(payload.sortedLinkColors.subarray(0, n * 4))
    widths.set(payload.sortedLinkWidths.subarray(0, n))
    const extras = new Map<number, number>()
    extraLinks.forEach((li, k) => {
      const at = n + k
      extras.set(li, at)
      links.set(payload.sortedLinks.subarray(li * 2, li * 2 + 2), at * 2)
      widths[at] = payload.sortedLinkWidths[li]
    })
    uploadedRef.current = { prefix: n, extras, key }
    for (const li of ego) {
      const at = uploadedIndex(li)
      colors.set(FOCUS_EDGE_RGBA, at * 4)
      widths[at] = payload.sortedLinkWidths[li] * 2.2
    }
    cosmos.setLinks(links)
    cosmos.setLinkColors(colors)
    cosmos.setLinkWidths(widths)
    cosmos.render()
    wake()

    edgeCountRef.current = n
    setVisibleEdgeCount(n)
    setEdgeCutoff(n > 0 ? payload.sortedSharedCounts[n - 1] : 0)
  }, [uploadedIndex, wake])

  // Resting highlight: the selected person's collaboration circle if any,
  // otherwise the min-degree filter. Hover temporarily replaces it.
  const applyBaseHighlight = useCallback(() => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return

    const selectedIndex = selectedNodeRef.current ? payload.nodeIndexById.get(selectedNodeRef.current) : undefined
    if (selectedIndex !== undefined) {
      const links = egoLinks(selectedIndex)
      cosmos.setConfigPartial({
        highlightedPointIndices: [selectedIndex, ...links.map(li => otherEnd(li, selectedIndex))],
        highlightedLinkIndices: links.map(uploadedIndex),
      })
    } else if (minDegreeRef.current > 0) {
      const threshold = minDegreeRef.current
      const indices: number[] = []
      for (let i = 0; i < payload.degrees.length; i += 1) {
        if (payload.degrees[i] >= threshold) indices.push(i)
      }
      cosmos.setConfigPartial({ highlightedPointIndices: indices, highlightedLinkIndices: undefined })
    } else {
      cosmos.setConfigPartial({ highlightedPointIndices: undefined, highlightedLinkIndices: undefined })
    }
    wake()
  }, [egoLinks, otherEnd, uploadedIndex, wake])

  // Hover highlight is pure GPU-side config driven by the precomputed incidence
  // map — O(degree), not O(edges).
  const applyHoverEdgeFocus = useCallback((index?: number) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return
    if (index === undefined) {
      applyBaseHighlight()
      return
    }
    const links = egoLinks(index).filter(li => uploadedIndex(li) >= 0)
    cosmos.setConfigPartial({
      highlightedPointIndices: [index, ...links.map(li => otherEnd(li, index))],
      highlightedLinkIndices: links.map(uploadedIndex),
    })
    wake()
  }, [applyBaseHighlight, egoLinks, otherEnd, uploadedIndex, wake])

  const applyPointScale = useCallback(() => {
    const cosmos = cosmosRef.current
    if (!cosmos) return
    const zoom = cosmos.getZoomLevel()
    if (awaitingReferenceRef.current && Number.isFinite(zoom) && zoom > 0) {
      awaitingReferenceRef.current = false
      zoomRefRef.current = zoom
      if (pendingFocusRef.current) {
        pendingFocusRef.current = false
        // Leave the zoom event first: the glide starts its own camera move.
        window.setTimeout(() => focusSelectionRef.current?.(true), 0)
      }
    }
    const reference = zoomRefRef.current
    if (!reference || !Number.isFinite(zoom)) return
    const damping = zoom > reference ? (reference / zoom) ** (1 - POINT_ZOOM_GROWTH) : 1
    cosmos.setConfigPartial({ pointSizeScale: POINT_SIZE_SCALE * damping })
  }, [])

  // Avatars and circle labels follow the camera. Circle labels hide while a
  // person is selected: their collaborator labels take over then.
  const updateOverlays = useCallback(() => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const container = containerRef.current
    if (!cosmos || !payload || !container) return
    const bounds = container.getBoundingClientRect()
    const onScreen = (x: number, y: number, margin: number) =>
      x >= margin && y >= HEADER_HEIGHT && x <= bounds.width - margin && y <= bounds.height - margin

    type Box = { left: number; right: number; top: number; bottom: number }
    const overlaps = (box: Box, boxes: Box[]) =>
      boxes.some(b => box.left < b.right && box.right > b.left && box.top < b.bottom && box.bottom > b.top)

    // Circle labels are placed first: there are few of them and they say the
    // most, while avatars cluster exactly at circle centers and would crowd
    // every label out. Avatars then fill the space the labels leave.
    const boxes: Box[] = []
    const nextTags: CommunityTag[] = []
    const communities = communitiesRef.current
    if (!selectedNodeRef.current && communities.length > 0) {
      const [originX] = cosmos.spaceToScreenPosition([0, 0])
      const [unitX] = cosmos.spaceToScreenPosition([1000, 0])
      const pxPerUnit = Math.abs(unitX - originX) / 1000
      const radiusOf = new Map<number, number>()
      const split = new Set<number>()
      for (const c of communities) {
        if (c.level !== 0) continue
        radiusOf.set(c.parent, c.radius)
        if (c.radius * pxPerUnit >= COMMUNITY_SPLIT_PX) split.add(c.parent)
      }
      const shown = communities.filter(c =>
        c.level === 0
          ? !split.has(c.parent) && c.radius * pxPerUnit >= COMMUNITY_MIN_PX
          : split.has(c.parent) && c.radius <= (radiusOf.get(c.parent) ?? 0) * SUB_COMMUNITY_MAX_SPREAD,
      )
      // Largest first, so a crowded spot keeps its biggest circle.
      shown.sort((a, b) => b.size - a.size)
      for (const c of shown) {
        const [x, y] = cosmos.spaceToScreenPosition([c.x, c.y])
        const title = c.people.slice(0, 2).map(id => payload.nodeLabels.get(id) ?? id).join(' · ')
        const work = c.works[0] ? displaySubjectName(c.works[0], nameModeRef.current) : ''
        const decade = c.level === 0 && c.year ? `${Math.floor(c.year / 10) * 10} 年代` : ''
        const subtitle = [work, decade].filter(Boolean).join(' · ')
        const width = Math.min(260, Math.max(title.length * 13, subtitle.length * 11) + 12)
        const box = { left: x - width / 2, right: x + width / 2, top: y - 18, bottom: y + 18 }
        if (!onScreen(box.left, box.top, 8) || !onScreen(box.right, box.bottom, 8)) continue
        if (overlaps(box, boxes)) continue
        boxes.push(box)
        nextTags.push({ id: c.id, level: c.level, title, subtitle, x, y })
      }
    }
    setCommunityTags(current => (current.length === 0 && nextTags.length === 0 ? current : nextTags))

    const relativeZoom = cosmos.getZoomLevel() / (zoomRefRef.current ?? cosmos.getZoomLevel())
    const growth = relativeZoom > 1 ? relativeZoom ** POINT_ZOOM_GROWTH : relativeZoom
    const size = Math.round(Math.min(AVATAR_MAX_SIZE, Math.max(AVATAR_MIN_SIZE, AVATAR_SIZE * growth)))
    const nextAvatars: AvatarSpot[] = []
    const minGap = (size + 4) ** 2
    for (const id of featuredRef.current) {
      const index = payload.nodeIndexById.get(id)
      if (index === undefined || missingAvatarsRef.current.has(id)) continue
      const [x, y] = cosmos.spaceToScreenPosition([payload.positions[index * 2], payload.positions[index * 2 + 1]])
      if (!onScreen(x, y, size / 2)) continue
      if (nextAvatars.some(a => (a.x - x) ** 2 + (a.y - y) ** 2 < minGap)) continue
      if (overlaps({ left: x - size / 2, right: x + size / 2, top: y - size / 2, bottom: y + size / 2 }, boxes)) continue
      nextAvatars.push({ id, x, y, size })
    }
    avatarsRef.current = nextAvatars
    setAvatars(nextAvatars)
  }, [])

  const markAvatarMissing = useCallback((id: string) => {
    missingAvatarsRef.current.add(id)
    updateOverlays()
  }, [updateOverlays])

  const updateLabels = useCallback(() => {
    updateOverlays()
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const container = containerRef.current
    if (!cosmos || !payload || !container || labelIndicesRef.current.length === 0) {
      setLabels(current => (current.length > 0 ? [] : current))
      return
    }

    const bounds = container.getBoundingClientRect()
    const next: GraphLabel[] = []
    const boxes: { left: number; right: number; top: number; bottom: number }[] = []
    labelIndicesRef.current.forEach((index, order) => {
      const id = payload.nodeIds[index]
      const label = payload.nodeLabels.get(id) ?? id
      const [x, y] = cosmos.spaceToScreenPosition([payload.positions[index * 2], payload.positions[index * 2 + 1]])
      const width = Math.min(180, Math.max(52, label.length * 12 + 18))
      const box = { left: x - width / 2, right: x + width / 2, top: y - 28, bottom: y - 4 }
      if (box.left < 8 || box.top < 76 || box.right > bounds.width - 8 || box.bottom > bounds.height - 8) return
      // The selected person's label always wins; neighbors skip on overlap.
      if (order > 0 && boxes.some(b => box.left < b.right && box.right > b.left && box.top < b.bottom && box.bottom > b.top)) return
      boxes.push(box)
      next.push({ id, label, x, y, center: order === 0 })
    })
    setLabels(next)
  }, [updateOverlays])

  useEffect(() => {
    let cancelled = false
    // Circle labels and avatars are extras; the galaxy works without either.
    loadCommunityLabels()
      .then(communities => {
        if (cancelled) return
        communitiesRef.current = communities
        updateOverlays()
      })
      .catch(() => {})
    loadFeaturedPeople()
      .then(people => {
        if (cancelled) return
        featuredRef.current = people
        updateOverlays()
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [updateOverlays])

  useEffect(() => {
    nameModeRef.current = personNameMode
    updateOverlays()
  }, [personNameMode, updateOverlays])

  const updateHoverLabelPosition = useCallback((nodeId = hoveredNodeRef.current) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    const el = hoverLabelRef.current
    if (!cosmos || !payload || !el || !nodeId) return
    const index = payload.nodeIndexById.get(nodeId)
    if (index === undefined) return
    const [x, y] = cosmos.spaceToScreenPosition([payload.positions[index * 2], payload.positions[index * 2 + 1]])
    el.style.left = `${x}px`
    el.style.top = `${y}px`
  }, [])

  // Stable show/hide hover label via DOM — avoids React re-renders on every hover.
  const showHoverLabel = useCallback((nodeId: string | null) => {
    hoveredNodeRef.current = nodeId
    const el = hoverLabelRef.current
    if (!el) return
    if (nodeId) {
      el.textContent = payloadRef.current?.nodeLabels.get(nodeId) ?? nodeId
      updateHoverLabelPosition(nodeId)
      el.classList.remove('opacity-0')
    } else {
      el.classList.add('opacity-0')
    }
  }, [updateHoverLabelPosition])

  const clearHoverEdgeFocus = useCallback(() => {
    highlightedPointerPositionRef.current = null
    showHoverLabel(null)
    applyHoverEdgeFocus()
  }, [applyHoverEdgeFocus, showHoverLabel])

  // Select = focus in place: highlight the collaboration circle, force its edges
  // visible, label the strongest neighbors and glide the camera to frame them.
  const focusSelection = useCallback((animate: boolean) => {
    const cosmos = cosmosRef.current
    const payload = payloadRef.current
    if (!cosmos || !payload) return
    const index = selectedNodeRef.current ? payload.nodeIndexById.get(selectedNodeRef.current) : undefined
    applyEdgeDensity(true)
    applyBaseHighlight()
    if (index === undefined) {
      cosmos.setConfigPartial({ focusedPointIndex: undefined })
      labelIndicesRef.current = []
      updateLabels()
      wake()
      return
    }
    const links = egoLinks(index)
    const neighbors = links.map(li => otherEnd(li, index))
    labelIndicesRef.current = [index, ...neighbors.slice(0, FOCUS_LABEL_LIMIT)]
    cosmos.setConfigPartial({ focusedPointIndex: index })
    if (animate) {
      // Glide to the person. Their collaborators often sit in other Leiden
      // communities, so framing the whole circle would zoom out to the galaxy;
      // the bright edges show where the circle reaches instead.
      // Two frames: the first lets cosmos.gl pick up a canvas resized by the
      // sidebar opening, so the glide centers on the new visible area.
      wake(FOCUS_CAMERA_MS + 100)
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
        cosmos.zoomToPointByIndex(index, FOCUS_CAMERA_MS, FOCUS_ZOOM, true, false)
        window.setTimeout(updateLabels, FOCUS_CAMERA_MS + 30)
      }))
    } else {
      updateLabels()
      wake()
    }
  }, [applyBaseHighlight, applyEdgeDensity, egoLinks, otherEnd, updateLabels, wake])

  useEffect(() => {
    applyEdgeDensityRef.current = () => applyEdgeDensity()
  }, [applyEdgeDensity])

  useEffect(() => {
    focusSelectionRef.current = focusSelection
  }, [focusSelection])

  const applyQuality = useCallback((level: number) => {
    qualityRef.current = level
    setQualityLevel(level)
    try {
      window.localStorage.setItem(QUALITY_STORAGE_KEY, String(level))
    } catch {
      // Not persisted; detection or adaptation runs again next visit.
    }
    cosmosRef.current?.setConfigPartial({
      pixelRatio: Math.min(QUALITY_LEVELS[level].pixelRatio, window.devicePixelRatio || 1),
    })
    applyEdgeDensity(true)
  }, [applyEdgeDensity])

  // Adaptive quality controller. Samples frame times only while cosmos.gl is
  // actually rendering (paused idle frames would read as fast), in windows of
  // >= 0.6 s and >= 3 frames so very slow devices still converge in seconds.
  useEffect(() => {
    let raf = 0
    let last = 0
    let windowStart = 0
    let samples: number[] = []
    let fastWindows = 0
    const tick = (now: number) => {
      raf = window.requestAnimationFrame(tick)
      const frames = cosmosRef.current as unknown as FrameControl | null
      if (!frames?.requestAnimationFrameId || document.hidden || edgeBudgetOverrideRef.current > 0) {
        last = 0
        windowStart = 0
        samples = []
        return
      }
      if (last) samples.push(now - last)
      last = now
      windowStart ||= now
      if (now - windowStart < 600 || samples.length < 3) return
      const sorted = samples.sort((a, b) => a - b)
      const median = sorted[Math.floor(sorted.length / 2)]
      samples = []
      windowStart = now
      const level = qualityRef.current
      if (median > SLOW_FRAME_MS && level < QUALITY_LEVELS.length - 1) {
        qualityFloorRef.current = Math.max(qualityFloorRef.current, level + 1)
        fastWindows = 0
        applyQuality(level + 1)
      } else if (median < FAST_FRAME_MS && level > qualityFloorRef.current) {
        fastWindows += 1
        if (fastWindows >= UPGRADE_WINDOWS) {
          fastWindows = 0
          applyQuality(level - 1)
        }
      } else {
        fastWindows = 0
      }
    }
    raf = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(raf)
  }, [applyQuality])

  // `?debug` exposes the renderer to scripts/gpu-bench.mjs; no effect otherwise.
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has('debug')) return
    const hook = window as unknown as { __galaxyDebug?: unknown }
    hook.__galaxyDebug = {
      cosmos: () => cosmosRef.current,
      payload: () => payloadRef.current,
      setEdgeBudget: (n: number) => {
        edgeBudgetOverrideRef.current = n
        applyEdgeDensity(true)
      },
      wake: (busyMs: number) => wake(busyMs),
      quality: () => qualityRef.current,
      setQuality: (level: number) => applyQuality(level),
    }
    return () => { delete hook.__galaxyDebug }
  }, [applyEdgeDensity, applyQuality, wake])

  useEffect(() => {
    onNodeClickRef.current = onNodeClick
    onBackgroundClickRef.current = onBackgroundClick
  }, [onBackgroundClick, onNodeClick])

  // cosmos.gl resizes its canvas inside a render frame, so a container resize
  // (window, or the docked sidebar opening) must wake the paused loop.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const observer = new ResizeObserver(() => {
      wake()
      window.requestAnimationFrame(() => {
        updateLabels()
        updateHoverLabelPosition()
      })
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [updateHoverLabelPosition, updateLabels, wake])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const cosmos = new CosmosGraph(container, {
      ...COSMOS_CONFIG,
      pixelRatio: Math.min(QUALITY_LEVELS[qualityRef.current].pixelRatio, window.devicePixelRatio || 1),
      onPointClick: (index: number) => {
        const nodeId = payloadRef.current?.nodeIds[index]
        if (nodeId) onNodeClickRef.current(nodeId)
      },
      onBackgroundClick: () => onBackgroundClickRef.current(),
      onPointMouseOver: (index: number) => {
        if (avatarHoverRef.current) return
        highlightedPointerPositionRef.current = lastPointerPositionRef.current
        showHoverLabel(payloadRef.current?.nodeIds[index] ?? null)
        applyHoverEdgeFocus(index)
      },
      onPointMouseOut: () => {
        if (avatarHoverRef.current) return
        clearHoverEdgeFocus()
      },
      onMouseMove: (_index: number | undefined, _position: [number, number] | undefined, event: MouseEvent) => {
        const nextPosition: [number, number] = [event.offsetX, event.offsetY]
        const highlightedPosition = highlightedPointerPositionRef.current
        if (highlightedPosition) {
          const dx = nextPosition[0] - highlightedPosition[0]
          const dy = nextPosition[1] - highlightedPosition[1]
          if (dx * dx + dy * dy > 36) clearHoverEdgeFocus()
        }
        lastPointerPositionRef.current = nextPosition
      },
      onZoomEnd: () => {
        applyEdgeDensityRef.current?.()
        applyPointScale()
        updateLabels()
        updateHoverLabelPosition()
      },
      onZoom: () => {
        applyPointScale()
        updateLabels()
        updateHoverLabelPosition()
      },
    })
    cosmosRef.current = cosmos

    // Any input over the canvas resumes rendering (hover detection runs per frame).
    const onInput = () => wake()
    container.addEventListener('pointermove', onInput, { passive: true })
    container.addEventListener('pointerdown', onInput, { passive: true })
    container.addEventListener('wheel', onInput, { passive: true })

    // Avatar hit-testing runs in the capture phase, ahead of cosmos.gl's own
    // canvas listeners; wheel and drag still reach the canvas untouched.
    const avatarAt = (event: MouseEvent) => {
      const bounds = container.getBoundingClientRect()
      const x = event.clientX - bounds.left
      const y = event.clientY - bounds.top
      return avatarsRef.current.find(a => (a.x - x) ** 2 + (a.y - y) ** 2 <= (a.size / 2 + 2) ** 2)
    }
    let downAt: [number, number] | null = null
    const onAvatarDown = (event: PointerEvent) => { downAt = [event.clientX, event.clientY] }
    const onAvatarClick = (event: MouseEvent) => {
      // A drag that ends over an avatar is a pan, not a click.
      const moved = downAt ? Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1]) : 0
      const spot = moved < 5 ? avatarAt(event) : undefined
      if (!spot) return
      event.stopPropagation()
      onNodeClickRef.current(spot.id)
    }
    const onAvatarMove = (event: PointerEvent) => {
      const spot = event.buttons === 0 ? avatarAt(event) : undefined
      if (spot?.id === avatarHoverRef.current) return
      avatarHoverRef.current = spot?.id ?? null
      container.style.cursor = spot ? 'pointer' : ''
      const index = spot ? payloadRef.current?.nodeIndexById.get(spot.id) : undefined
      if (spot && index !== undefined) {
        highlightedPointerPositionRef.current = null
        showHoverLabel(spot.id)
        applyHoverEdgeFocus(index)
      } else {
        clearHoverEdgeFocus()
      }
    }
    container.addEventListener('pointerdown', onAvatarDown, { capture: true, passive: true })
    container.addEventListener('click', onAvatarClick, { capture: true })
    container.addEventListener('pointermove', onAvatarMove, { capture: true, passive: true })
    return () => {
      container.removeEventListener('pointermove', onInput)
      container.removeEventListener('pointerdown', onInput)
      container.removeEventListener('wheel', onInput)
      container.removeEventListener('pointerdown', onAvatarDown, { capture: true })
      container.removeEventListener('click', onAvatarClick, { capture: true })
      container.removeEventListener('pointermove', onAvatarMove, { capture: true })
      window.clearTimeout(idleTimerRef.current)
      cosmos.destroy()
      cosmosRef.current = null
    }
  }, [applyHoverEdgeFocus, applyPointScale, clearHoverEdgeFocus, showHoverLabel, updateHoverLabelPosition, updateLabels, wake])

  useEffect(() => {
    const cosmos = cosmosRef.current
    if (!cosmos) return

    payloadRef.current = payload
    cosmos.setPointPositions(payload.positions)
    cosmos.setPointColors(payload.pointColors)
    cosmos.setPointSizes(payload.pointSizes)
    // The first load always frames the core once, even for a deep-linked
    // person, so the point-size reference zoom is the same for every visit.
    // A deep link glides to its person only once that fit has landed
    // (applyPointScale), or after a fallback delay if no zoom event comes.
    let fallback = 0
    window.setTimeout(() => {
      const firstLoad = zoomRefRef.current === null
      if (firstLoad || !selectedNodeRef.current) {
        awaitingReferenceRef.current = firstLoad
        pendingFocusRef.current = firstLoad && Boolean(selectedNodeRef.current)
        cosmos.fitViewByPointPositions(corePositions(payload), 0, CORE_FIT_PADDING, false)
        applyPointScale()
      }
      if (pendingFocusRef.current) {
        fallback = window.setTimeout(() => {
          if (!pendingFocusRef.current) return
          pendingFocusRef.current = false
          focusSelection(true)
        }, 1500)
      } else {
        focusSelection(Boolean(selectedNodeRef.current))
      }
      wake()
    }, 0)

    window.requestAnimationFrame(() => {
      recordRuntimeMetric('cosmos-ready', {
        level: 'global',
        nodes: payload.nodeIds.length,
        totalEdges: payload.totalEdgeCount,
        visibleEdges: edgeCountRef.current,
        edgeCutoff: edgeCountRef.current > 0 ? payload.sortedSharedCounts[edgeCountRef.current - 1] : 0,
      })
    })
    return () => window.clearTimeout(fallback)
    // focusSelection is stable for a given payload; selection changes are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload])

  useEffect(() => {
    if (selectedNodeRef.current === selectedNode) return
    selectedNodeRef.current = selectedNode
    focusSelection(true)
  }, [focusSelection, selectedNode])

  const edgeBudgetDisplay = edgeBudgetForSlider(edgeBudgetSlider, payload.totalEdgeCount).toLocaleString()

  return (
    <div className="relative h-full w-full bg-[#0b0c10]">
      <div ref={containerRef} className="w-full h-full" onMouseLeave={clearHoverEdgeFocus} />

      {/* Hover label — DOM-only, no React re-render on hover */}
      <div
        ref={hoverLabelRef}
        className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-[140%] whitespace-nowrap rounded-md bg-zinc-900 px-2.5 py-1 text-sm text-zinc-100 opacity-0 shadow-lg ring-1 ring-white/10 transition-opacity duration-75"
      />

      <div className="pointer-events-none absolute inset-0 z-10">
        {avatars.map(spot => (
          <Avatar key={spot.id} spot={spot} onMissing={markAvatarMissing} />
        ))}
        {communityTags.map(tag => (
          <div
            key={tag.id}
            className="absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-md bg-zinc-950/75 px-2 py-1 text-center leading-snug ring-1 ring-white/[0.06] backdrop-blur-[2px]"
            style={{ left: tag.x, top: tag.y }}
          >
            <div className={tag.level === 0 ? 'text-[13px] font-medium text-zinc-100' : 'text-xs text-zinc-200'}>
              {tag.title}
            </div>
            {tag.subtitle && <div className="text-[11px] text-zinc-400">{tag.subtitle}</div>}
          </div>
        ))}
        {labels.map(label => (
          <div
            key={label.id}
            className={`absolute -translate-x-1/2 -translate-y-[150%] rounded px-1.5 py-0.5 leading-tight ${
              label.center
                ? 'bg-[#f5c76b] text-sm font-semibold text-zinc-950'
                : 'bg-zinc-950/80 text-xs text-zinc-200'
            }`}
            style={{ left: label.x, top: label.y }}
          >
            {label.label}
          </div>
        ))}
      </div>

      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-1 rounded-md bg-zinc-950/80 py-1 pl-3 pr-1 text-xs text-zinc-400 ring-1 ring-white/[0.08]">
        <span>
          {payload.nodeIds.length.toLocaleString()} 人 · {payload.totalEdgeCount.toLocaleString()} 条骨干合作
        </span>
        <Popover.Root>
          <Popover.Trigger className={iconButton} aria-label="图谱设置">
            <Settings2 size={15} />
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content side="top" align="start" sideOffset={8} className={`${panelShell} z-[60] w-72 space-y-4 p-3 text-xs text-zinc-400`}>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>只突出合作者数 ≥</span>
                  <span className="tabular-nums text-zinc-100">{minDegree === 0 ? '不限' : minDegree}</span>
                </div>
                <Slider.Root
                  min={0}
                  max={300}
                  step={5}
                  value={[minDegree]}
                  onValueChange={([value]) => {
                    setMinDegree(value)
                    minDegreeRef.current = value
                    applyBaseHighlight()
                  }}
                  className={sliderRoot}
                >
                  <Slider.Track className={sliderTrack}><Slider.Range className={sliderRange} /></Slider.Track>
                  <Slider.Thumb className={sliderThumb} aria-label="合作者数下限" />
                </Slider.Root>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>同时显示的连线</span>
                  <span className="tabular-nums text-zinc-100">
                    {edgeBudgetSlider === 0 ? `自动（${visibleEdgeCount.toLocaleString()}）` : edgeBudgetDisplay}
                  </span>
                </div>
                <Slider.Root
                  min={0}
                  max={100}
                  step={1}
                  value={[edgeBudgetSlider]}
                  onValueChange={([slider]) => {
                    setEdgeBudgetSlider(slider)
                    edgeBudgetOverrideRef.current = slider === 0
                      ? 0
                      : edgeBudgetForSlider(slider, payloadRef.current?.totalEdgeCount ?? MIN_EDGE_BUDGET)
                    applyEdgeDensity(true)
                  }}
                  className={sliderRoot}
                >
                  <Slider.Track className={sliderTrack}><Slider.Range className={sliderRange} /></Slider.Track>
                  <Slider.Thumb className={sliderThumb} aria-label="连线数量" />
                </Slider.Root>
                <div className="text-zinc-500">自动：缩放越近显示越少、越强的连线（当前最少 {edgeCutoff} 部共同作品）。</div>
              </div>
              <div className="flex justify-between border-t border-white/[0.06] pt-3">
                <span>画质（按设备性能自动调节）</span>
                <span className="tabular-nums text-zinc-100">
                  {qualityLevel === 0 ? '最高' : `降 ${qualityLevel} 档`}
                </span>
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
    </div>
  )
}
