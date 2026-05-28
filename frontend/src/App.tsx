import { Suspense, lazy, useState, useEffect, useCallback } from 'react'
import Graph from 'graphology'
import { loadLevel, loadPersonGalaxy, type Level, type LevelData } from './data/loader'
import { buildGraph } from './data/graphBuilder'
import { SearchBar } from './components/SearchBar'
import { NodePanel } from './components/NodePanel'
import { panelShell, segmentedButtonClass, segmentedGroupClass } from './components/ui'
import { getInitialPersonNameMode, PERSON_NAME_MODE_KEY } from './data/personNames'
import type { PersonNameMode } from './types'

type ViewMode = 'galaxy' | 'constellation'
type ConstellationMode = 'path' | 'compare'
type GraphLevel = Exclude<Level, 'person'>

const CosmosGalaxyView = lazy(() => import('./components/CosmosGalaxyView').then(module => ({
  default: module.CosmosGalaxyView,
})))
const ConstellationView = lazy(() => import('./components/ConstellationView').then(module => ({
  default: module.ConstellationView,
})))

const PERSON_GALAXY_LIMIT_DEFAULT = 120
const PERSON_GALAXY_MIN_SHARED_DEFAULT = 1
const PERSON_GALAXY_EXPANSION_LIMIT = 36
const PERSON_GALAXY_EXPANSION_SCALE = 0.34

const GRAPH_LEVELS: GraphLevel[] = ['global', 'l0', 'l1']

const LEVEL_LABELS: Record<Level, string> = {
  person: '个人星系',
  global: '全量星系',
  l0: '核心视图',
  l1: '细节视图',
}

function PersonNameModeToggle({
  mode,
  onChange,
}: {
  mode: PersonNameMode
  onChange: (mode: PersonNameMode) => void
}) {
  return (
    <div className={segmentedGroupClass}>
      {(['original', 'cn', 'tw'] as const).map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={segmentedButtonClass(mode === option, 'cyan')}
        >
          {option === 'original' ? '原名' : option === 'cn' ? '简中' : '繁中'}
        </button>
      ))}
    </div>
  )
}

function GraphLevelToggle({
  level,
  onChange,
}: {
  level: Level
  onChange: (level: GraphLevel) => void
}) {
  return (
    <div className={segmentedGroupClass}>
      {GRAPH_LEVELS.map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={segmentedButtonClass(level === option, 'slate')}
          title={option === 'global'
            ? 'Sparse global graph'
            : option === 'l0'
              ? 'Dense core graph'
              : 'Mid-density detail graph'}
        >
          {LEVEL_LABELS[option]}
        </button>
      ))}
    </div>
  )
}

function ViewLoading({ label }: { label: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-[#0a0a0f] text-sm text-slate-500">
      {label}
    </div>
  )
}

interface AppRoute {
  view: ViewMode
  personId?: string
  graphLevel?: GraphLevel
  constellationMode?: ConstellationMode
  pathFrom?: string
  pathTo?: string
}

function readGraphLevel(value: string | null): GraphLevel {
  return value === 'l0' || value === 'l1' ? value : 'global'
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
  return { view: 'galaxy', graphLevel: readGraphLevel(url.searchParams.get('level')) }
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

function graphLevelPath(graphLevel: GraphLevel) {
  return graphLevel === 'global' ? '/' : `/?level=${graphLevel}`
}

function edgeKey(source: string, target: string) {
  return source < target ? `${source}|${target}` : `${target}|${source}`
}

function mergePersonExpansion(baseData: LevelData, anchorId: string, expansionData: LevelData): LevelData {
  const nodeById = new Map(baseData.nodes.map(node => [node.id, { ...node }]))
  const anchor = nodeById.get(anchorId)
  if (!anchor) return baseData

  const anchorX = anchor.x ?? 0
  const anchorY = anchor.y ?? 0
  for (const node of expansionData.nodes) {
    if (node.id === anchorId || nodeById.has(node.id)) continue
    nodeById.set(node.id, {
      ...node,
      isCenter: false,
      expandedFrom: anchorId,
      x: anchorX + (node.x ?? 0) * PERSON_GALAXY_EXPANSION_SCALE,
      y: anchorY + (node.y ?? 0) * PERSON_GALAXY_EXPANSION_SCALE,
    })
  }

  const edges = [...baseData.edges]
  const existingEdges = new Set(edges.map(edge => edgeKey(edge.source, edge.target)))
  for (const edge of expansionData.edges) {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) continue
    const key = edgeKey(edge.source, edge.target)
    if (existingEdges.has(key)) continue
    edges.push({ ...edge, expandedFrom: anchorId })
    existingEdges.add(key)
  }

  return { nodes: Array.from(nodeById.values()), edges }
}

export default function App() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [level, setLevel] = useState<Level>('global')
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [personGraphData, setPersonGraphData] = useState<LevelData | null>(null)
  const [expandedNeighborId, setExpandedNeighborId] = useState<string | null>(null)
  const [expandingNeighborId, setExpandingNeighborId] = useState<string | null>(null)
  const [route, setRoute] = useState<AppRoute>(readRoute)
  const [view, setView] = useState<ViewMode>(() => route.view)
  const [personNameMode, setPersonNameMode] = useState<PersonNameMode>(getInitialPersonNameMode)
  const [personGalaxyLimit, setPersonGalaxyLimit] = useState(PERSON_GALAXY_LIMIT_DEFAULT)
  const [personGalaxyMinShared, setPersonGalaxyMinShared] = useState(PERSON_GALAXY_MIN_SHARED_DEFAULT)

  useEffect(() => {
    window.localStorage.setItem(PERSON_NAME_MODE_KEY, personNameMode)
  }, [personNameMode])

  useEffect(() => {
    function handlePopState() {
      setRoute(readRoute())
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const loadPersonView = useCallback((personId: string, updateUrl = true) => {
    const nextRoute = { view: 'galaxy' as const, personId }
    setRoute(nextRoute)
    if (updateUrl) {
      writeRoute(`/person/${encodeURIComponent(personId)}`)
    }
  }, [])

  const loadGraphLevelView = useCallback((graphLevel: GraphLevel = 'global', updateUrl = true) => {
    const nextRoute = { view: 'galaxy' as const, graphLevel }
    setRoute(nextRoute)
    if (updateUrl) {
      writeRoute(graphLevelPath(graphLevel))
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function applyRoute() {
      if (route.view === 'constellation') {
        setView('constellation')
        setLoading(false)
        return
      }

      setView('galaxy')
      setLoading(true)

      if (route.personId) {
        try {
          const data = await loadPersonGalaxy(route.personId, {
            limit: personGalaxyLimit,
            minShared: personGalaxyMinShared,
          })
          if (cancelled) return
          setGraph(buildGraph(data, 'person'))
          setLevel('person')
          setSelectedNode(route.personId)
          setPersonGraphData(data)
          setExpandedNeighborId(null)
          setExpandingNeighborId(null)
        } catch {
          if (cancelled) return
          const data = await loadLevel('global')
          if (cancelled) return
          setGraph(buildGraph(data, 'global'))
          setLevel('global')
          setSelectedNode(null)
          setPersonGraphData(null)
          setExpandedNeighborId(null)
          setExpandingNeighborId(null)
          setRoute({ view: 'galaxy' })
          writeRoute('/', true)
        } finally {
          if (!cancelled) setLoading(false)
        }
        return
      }

      const graphLevel = route.graphLevel ?? 'global'
      const data = await loadLevel(graphLevel)
      if (cancelled) return
      setGraph(buildGraph(data, graphLevel))
      setLevel(graphLevel)
      setSelectedNode(null)
      setPersonGraphData(null)
      setExpandedNeighborId(null)
      setExpandingNeighborId(null)
      setLoading(false)
    }

    void applyRoute()
    return () => { cancelled = true }
  }, [personGalaxyLimit, personGalaxyMinShared, route])

  const handleNodeClick = useCallback((nodeId: string) => {
    void loadPersonView(nodeId)
  }, [loadPersonView])

  const handleSearchSelect = useCallback((entry: { id: string }) => {
    void loadPersonView(entry.id)
  }, [loadPersonView])

  const handleGraphLevelChange = useCallback((nextLevel: GraphLevel) => {
    void loadGraphLevelView(nextLevel)
  }, [loadGraphLevelView])

  const handleConstellationNodeClick = useCallback((nodeId: string) => {
    setView('galaxy')
    void loadPersonView(nodeId)
  }, [loadPersonView])

  const openConstellation = useCallback(() => {
    setView('constellation')
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
    setView('constellation')
    setRoute({
      view: 'constellation',
      constellationMode: 'compare',
      pathFrom: personAId,
      pathTo: personBId,
    })
    writeRoute(constellationPath('compare', personAId, personBId))
  }, [])

  const handleToggleNeighborExpansion = useCallback(async (neighborId: string) => {
    if (level !== 'person' || !personGraphData) return

    if (expandedNeighborId === neighborId) {
      setGraph(buildGraph(personGraphData, 'person'))
      setExpandedNeighborId(null)
      setExpandingNeighborId(null)
      return
    }

    setExpandingNeighborId(neighborId)
    try {
      const expansionData = await loadPersonGalaxy(neighborId, {
        limit: PERSON_GALAXY_EXPANSION_LIMIT,
        minShared: personGalaxyMinShared,
      })
      const mergedData = mergePersonExpansion(personGraphData, neighborId, expansionData)
      setGraph(buildGraph(mergedData, 'person'))
      setExpandedNeighborId(neighborId)
    } finally {
      setExpandingNeighborId(null)
    }
  }, [expandedNeighborId, level, personGalaxyMinShared, personGraphData])

  const selectedNodeAttrs = selectedNode && graph?.hasNode(selectedNode)
    ? graph.getNodeAttributes(selectedNode)
    : null

  const selectedNodeNeighbors = selectedNode && graph?.hasNode(selectedNode)
    ? graph.neighbors(selectedNode)
      .map(id => {
        const edgeKey = graph.edge(selectedNode, id)
        const edgeAttrs = edgeKey ? graph.getEdgeAttributes(edgeKey) : {}
        return {
          id,
          attrs: graph.getNodeAttributes(id),
          sharedWorksCount: Number(edgeAttrs.sharedWorksCount ?? 0),
          collaborationScore: Number(edgeAttrs.collaborationScore ?? 0),
          firstYear: (edgeAttrs.firstYear as number) ?? undefined,
          lastYear: (edgeAttrs.lastYear as number) ?? undefined,
        }
      })
      .sort((a, b) => b.sharedWorksCount - a.sharedWorksCount)
      .slice(0, personGalaxyLimit)
    : []

  const selectedNodeNeighborTotal = selectedNode && graph?.hasNode(selectedNode)
    ? graph.neighbors(selectedNode).length
    : 0

  if (view === 'constellation') {
    return (
      <Suspense fallback={<ViewLoading label="Loading constellation…" />}>
        <ConstellationView
          key={`${route.constellationMode ?? 'path'}|${route.pathFrom ?? ''}|${route.pathTo ?? ''}`}
          mode={route.constellationMode ?? 'path'}
          initialPersonAId={route.pathFrom}
          initialPersonBId={route.pathTo}
          onNodeClick={handleConstellationNodeClick}
          onRouteChange={handleConstellationRouteChange}
          personNameMode={personNameMode}
          onPersonNameModeChange={setPersonNameMode}
          onBack={() => {
            setView('galaxy')
            if (selectedNode) {
              setRoute({ view: 'galaxy', personId: selectedNode })
              writeRoute(`/person/${encodeURIComponent(selectedNode)}`)
            } else {
              setRoute({ view: 'galaxy' })
              writeRoute('/')
            }
          }}
        />
      </Suspense>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-[#0a0a0f] text-slate-500 text-sm">
        Loading galaxy…
      </div>
    )
  }

  return (
    <div className="relative w-full h-full">
      {graph && (
        <Suspense fallback={<ViewLoading label="Loading graph renderer…" />}>
          <CosmosGalaxyView
            graph={graph}
            onNodeClick={handleNodeClick}
            level={level}
            selectedNode={selectedNode}
            personNameMode={personNameMode}
            minSharedFloor={level === 'person' ? personGalaxyMinShared : undefined}
            onBackToGlobal={() => loadGraphLevelView('global')}
          />
        </Suspense>
      )}

      <div className="absolute top-4 left-4 right-4 flex items-center gap-3 z-30 pointer-events-none">
        <div className={`${panelShell} flex shrink-0 items-center gap-3 px-3 py-2`}>
          <div className="h-8 w-1 rounded-full bg-[#f09199]" />
          <div>
            <div className="whitespace-nowrap text-sm font-semibold tracking-[0.22em] text-slate-100 uppercase">
              Staff Galaxy
            </div>
            <div className="whitespace-nowrap text-[10px] uppercase tracking-[0.16em] text-[#d98d88]">
              Bangumi Archive
            </div>
          </div>
        </div>
        <div className="pointer-events-auto">
          <SearchBar onSelect={handleSearchSelect} personNameMode={personNameMode} className="w-64" />
        </div>
        <div className="pointer-events-auto">
          <button
            type="button"
            onClick={openConstellation}
            className={`${panelShell} shrink-0 whitespace-nowrap px-3 py-2 text-xs text-slate-300 transition-colors hover:border-[#6baae8]/45 hover:text-[#d9ecff]`}
          >
            关系星图
          </button>
        </div>
        <div className="pointer-events-auto ml-auto">
          <GraphLevelToggle level={level} onChange={handleGraphLevelChange} />
        </div>
        <div className="hidden rounded-full border border-[#f09199]/25 bg-black/30 px-2 py-1 text-[10px] tracking-wider text-slate-400 backdrop-blur lg:block">
          {LEVEL_LABELS[level]}
        </div>
        <div className="pointer-events-auto">
          <PersonNameModeToggle mode={personNameMode} onChange={setPersonNameMode} />
        </div>
      </div>

      {selectedNode && selectedNodeAttrs && (
        <NodePanel
          nodeId={selectedNode}
          nodeAttrs={selectedNodeAttrs}
          neighbors={selectedNodeNeighbors}
          neighborTotal={selectedNodeNeighborTotal}
          neighborLimit={personGalaxyLimit}
          neighborMinShared={personGalaxyMinShared}
          onNeighborLimitChange={setPersonGalaxyLimit}
          onNeighborMinSharedChange={setPersonGalaxyMinShared}
          personNameMode={personNameMode}
          onPersonNameModeChange={setPersonNameMode}
          onClose={() => setSelectedNode(null)}
          onNodeClick={handleNodeClick}
          onCompare={handleCompareCollaborator}
          expandedNeighborId={expandedNeighborId}
          expandingNeighborId={expandingNeighborId}
          onToggleNeighborExpansion={handleToggleNeighborExpansion}
        />
      )}
    </div>
  )
}
