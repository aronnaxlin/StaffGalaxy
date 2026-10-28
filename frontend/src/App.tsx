import { Suspense, lazy, useState, useEffect, useCallback, useMemo } from 'react'
import { loadManifest, loadPersonGalaxy, type LevelData } from './data/loader'
import { loadGlobalGraph, type GlobalGraphData } from './data/graphBuffers'
import { Popover, Tooltip } from 'radix-ui'
import { Info } from 'lucide-react'
import { SearchBar } from './components/SearchBar'
import { PersonSidebar } from './components/PersonSidebar'
import { NameModeToggle } from './components/NameModeToggle'
import { iconButton, mutedLink, panelShell, segmentedButtonClass, segmentedGroupClass } from './components/ui'
import { getInitialPersonNameMode, PERSON_NAME_MODE_KEY } from './data/personNames'
import { buildGlobalPayload } from './data/cosmosPayload'
import type { Manifest, PersonNameMode } from './types'

type ViewMode = 'galaxy' | 'constellation'
type ConstellationMode = 'path' | 'compare'

const CosmosGalaxyView = lazy(() => import('./components/CosmosGalaxyView').then(module => ({
  default: module.CosmosGalaxyView,
})))
const ConstellationView = lazy(() => import('./components/ConstellationView').then(module => ({
  default: module.ConstellationView,
})))

const NEIGHBOR_LIMIT_DEFAULT = 120
const NEIGHBOR_MIN_SHARED_DEFAULT = 1

function ViewLoading({ label }: { label: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-[#0b0c10] text-sm text-zinc-500">
      {label}
    </div>
  )
}

function DataSourceInfo({ manifest }: { manifest: Manifest | null }) {
  const snapshot = manifest?.snapshot
  return (
    <Popover.Root>
      <Popover.Trigger className={iconButton} aria-label="数据来源">
        <Info size={16} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className={`${panelShell} z-[60] w-80 space-y-2 p-3 text-sm leading-relaxed text-zinc-300`}>
          <div className="font-medium text-zinc-100">数据来源</div>
          <p>
            Bangumi Archive 快照{snapshot ? `（${snapshot.archiveCreatedAt?.slice(0, 10)}）` : ''}，存放在 Neo4j 知识图谱中。
          </p>
          <p className="text-zinc-400">
            人物、职位记录由社区维护，可能有缺失、滞后或同名歧义；连线只表示快照中能查到的共同动画职位。
          </p>
          {snapshot?.sourceUrl && (
            <a href={snapshot.sourceUrl} target="_blank" rel="noopener noreferrer" className={mutedLink}>
              {snapshot.archiveName}
            </a>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}

interface AppRoute {
  view: ViewMode
  personId?: string
  constellationMode?: ConstellationMode
  pathFrom?: string
  pathTo?: string
}

function readRoute(): AppRoute {
  const url = new URL(window.location.href)
  const personMatch = url.pathname.match(/^\/person\/([^/]+)$/)
  if (personMatch) {
    return { view: 'galaxy', personId: decodeURIComponent(personMatch[1]) }
  }
  if (url.pathname === '/path' || url.pathname === '/compare') {
    return {
      view: 'constellation',
      constellationMode: url.pathname === '/compare' ? 'compare' : 'path',
      pathFrom: url.searchParams.get('from') ?? url.searchParams.get('a') ?? undefined,
      pathTo: url.searchParams.get('to') ?? url.searchParams.get('b') ?? undefined,
    }
  }
  return { view: 'galaxy' }
}

function writeRoute(path: string, replace = false) {
  const method = replace ? 'replaceState' : 'pushState'
  window.history[method](null, '', path)
}

function constellationPath(mode: ConstellationMode, personAId?: string | null, personBId?: string | null) {
  const basePath = mode === 'compare' ? '/compare' : '/path'
  if (!personAId || !personBId) return basePath
  return `${basePath}?from=${encodeURIComponent(personAId)}&to=${encodeURIComponent(personBId)}`
}

export default function App() {
  const [globalData, setGlobalData] = useState<GlobalGraphData | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [route, setRoute] = useState<AppRoute>(readRoute)
  const [personNameMode, setPersonNameMode] = useState<PersonNameMode>(getInitialPersonNameMode)
  const [neighborLimit, setNeighborLimit] = useState(NEIGHBOR_LIMIT_DEFAULT)
  const [neighborMinShared, setNeighborMinShared] = useState(NEIGHBOR_MIN_SHARED_DEFAULT)
  // Tagged with the request it answers, so a stale list is never shown while
  // the next one loads.
  const [neighborResult, setNeighborResult] = useState<{ key: string; data: LevelData } | null>(null)
  const [manifest, setManifest] = useState<Manifest | null>(null)

  // Selection is part of the URL (/person/:id) but never swaps the scene: the
  // galaxy stays loaded and focuses the person in place.
  const selectedNode = route.view === 'galaxy' ? route.personId ?? null : null
  const neighborKey = selectedNode ? `${selectedNode}|${neighborLimit}|${neighborMinShared}` : null
  const neighborData = neighborResult && neighborResult.key === neighborKey ? neighborResult.data : null

  useEffect(() => {
    let cancelled = false
    loadManifest()
      .then(data => { if (!cancelled) setManifest(data) })
      .catch(() => { if (!cancelled) setManifest(null) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    window.localStorage.setItem(PERSON_NAME_MODE_KEY, personNameMode)
  }, [personNameMode])

  useEffect(() => {
    const handlePopState = () => setRoute(readRoute())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const needsGalaxy = route.view === 'galaxy'
  useEffect(() => {
    if (!needsGalaxy || globalData) return
    let cancelled = false
    loadManifest()
      .then(loadGlobalGraph)
      .then(data => { if (!cancelled) setGlobalData(data) })
      .catch(error => {
        console.error('Failed to load global graph', error)
        if (!cancelled) setLoadError(true)
      })
    return () => { cancelled = true }
  }, [globalData, needsGalaxy])

  // Collaborator list for the side panel. People outside the galaxy have no
  // backbone neighbors (404); the panel then shows an empty list.
  useEffect(() => {
    if (!selectedNode || !neighborKey) return
    let cancelled = false
    loadPersonGalaxy(selectedNode, { limit: neighborLimit, minShared: neighborMinShared })
      .then(data => { if (!cancelled) setNeighborResult({ key: neighborKey, data }) })
      .catch(() => { if (!cancelled) setNeighborResult({ key: neighborKey, data: { nodes: [], edges: [] } }) })
    return () => { cancelled = true }
  }, [neighborKey, neighborLimit, neighborMinShared, selectedNode])

  const payload = useMemo(
    () => (globalData ? buildGlobalPayload(globalData, personNameMode) : null),
    [globalData, personNameMode],
  )

  const selectPerson = useCallback((personId: string) => {
    setRoute({ view: 'galaxy', personId })
    writeRoute(`/person/${encodeURIComponent(personId)}`)
  }, [])

  const clearSelection = useCallback(() => {
    setRoute(current => (current.view === 'galaxy' && current.personId ? { view: 'galaxy' } : current))
    if (window.location.pathname !== '/') writeRoute('/')
  }, [])

  const openConstellation = useCallback(() => {
    setRoute({ view: 'constellation', constellationMode: 'path' })
    writeRoute('/path')
  }, [])

  const handleConstellationRouteChange = useCallback((personAId: string | null, personBId: string | null) => {
    if (personAId && personBId) {
      const mode = route.constellationMode ?? 'path'
      const nextPath = constellationPath(mode, personAId, personBId)
      const currentPath = `${window.location.pathname}${window.location.search}`
      setRoute({ view: 'constellation', constellationMode: mode, pathFrom: personAId, pathTo: personBId })
      writeRoute(nextPath, currentPath === nextPath)
    }
  }, [route.constellationMode])

  const handleCompareCollaborator = useCallback((personAId: string, personBId: string) => {
    setRoute({ view: 'constellation', constellationMode: 'compare', pathFrom: personAId, pathTo: personBId })
    writeRoute(constellationPath('compare', personAId, personBId))
  }, [])

  const selectedNodeAttrs = useMemo(() => {
    if (!selectedNode) return null
    const center = neighborData?.nodes.find(node => node.isCenter)
    if (center) return center as unknown as Record<string, unknown>
    const index = globalData?.nodeIndexById.get(selectedNode)
    return index !== undefined ? (globalData!.meta[index] as unknown as Record<string, unknown>) : {}
  }, [globalData, neighborData, selectedNode])

  const neighbors = useMemo(() => {
    if (!selectedNode || !neighborData) return []
    const edgeByNeighbor = new Map(neighborData.edges.map(edge => [edge.target, edge]))
    return neighborData.nodes
      .filter(node => !node.isCenter)
      .map(node => {
        const edge = edgeByNeighbor.get(node.id)
        return {
          id: node.id,
          attrs: node as unknown as Record<string, unknown>,
          sharedWorksCount: edge?.sharedWorksCount ?? node.sharedWorksCount ?? 0,
          collaborationScore: edge?.collaborationScore ?? node.collaborationScore ?? 0,
          firstYear: edge?.firstYear ?? undefined,
          lastYear: edge?.lastYear ?? undefined,
        }
      })
      .sort((a, b) => b.sharedWorksCount - a.sharedWorksCount)
  }, [neighborData, selectedNode])

  if (route.view === 'constellation') {
    return (
      <Suspense fallback={<ViewLoading label="Loading constellation…" />}>
        <ConstellationView
          key={`${route.constellationMode ?? 'path'}|${route.pathFrom ?? ''}|${route.pathTo ?? ''}`}
          mode={route.constellationMode ?? 'path'}
          initialPersonAId={route.pathFrom}
          initialPersonBId={route.pathTo}
          onNodeClick={selectPerson}
          onRouteChange={handleConstellationRouteChange}
          personNameMode={personNameMode}
          onPersonNameModeChange={setPersonNameMode}
          onBack={() => {
            setRoute({ view: 'galaxy' })
            writeRoute('/')
          }}
        />
      </Suspense>
    )
  }

  if (!payload) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b0c10] text-sm text-zinc-500">
        {loadError ? '星系加载失败，请检查后端与 Neo4j 是否在运行。' : 'Loading galaxy…'}
      </div>
    )
  }

  return (
    <Tooltip.Provider delayDuration={300}>
      <div className="flex h-full w-full">
      {/* The sidebar is docked (not floating) so the galaxy's visible center is
          the canvas center: camera glides land on the person, uncovered. */}
      <div className="relative h-full min-w-0 flex-1">
        <Suspense fallback={<ViewLoading label="Loading graph renderer…" />}>
          <CosmosGalaxyView
            payload={payload}
            selectedNode={selectedNode}
            onNodeClick={selectPerson}
            onBackgroundClick={clearSelection}
          />
        </Suspense>

        <header className="pointer-events-none absolute inset-x-4 top-3 z-50 flex items-center gap-3">
          <div className="pointer-events-auto flex items-center gap-3">
            <span className="whitespace-nowrap text-sm font-semibold text-zinc-100">Staff Galaxy</span>
            <SearchBar onSelect={entry => selectPerson(entry.id)} personNameMode={personNameMode} className="w-72" />
          </div>
          <div className="pointer-events-auto ml-auto flex items-center gap-2">
            <div className={segmentedGroupClass}>
              <span className={segmentedButtonClass(true)}>星系</span>
              <button type="button" onClick={openConstellation} className={segmentedButtonClass(false)}>
                关系星图
              </button>
            </div>
            <NameModeToggle mode={personNameMode} onChange={setPersonNameMode} />
            <DataSourceInfo manifest={manifest} />
          </div>
        </header>
      </div>

        {selectedNode && selectedNodeAttrs && (
          <PersonSidebar
            personId={selectedNode}
            galaxyAttrs={selectedNodeAttrs}
            neighbors={neighbors}
            neighborLimit={neighborLimit}
            neighborMinShared={neighborMinShared}
            onNeighborLimitChange={setNeighborLimit}
            onNeighborMinSharedChange={setNeighborMinShared}
            nameMode={personNameMode}
            onClose={clearSelection}
            onSelectPerson={selectPerson}
            onCompare={handleCompareCollaborator}
          />
        )}
      </div>
    </Tooltip.Provider>
  )
}
