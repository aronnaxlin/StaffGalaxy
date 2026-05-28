import { useState, useEffect, useCallback } from 'react'
import Graph from 'graphology'
import { loadLevel, loadPersonGalaxy, type Level } from './data/loader'
import { buildGraph } from './data/graphBuilder'
import { CosmosGalaxyView } from './components/CosmosGalaxyView'
import { ConstellationView } from './components/ConstellationView'
import { SearchBar } from './components/SearchBar'
import { NodePanel } from './components/NodePanel'
import { getInitialPersonNameMode, PERSON_NAME_MODE_KEY } from './data/personNames'
import type { PersonNameMode } from './types'

type ViewMode = 'galaxy' | 'constellation'
type ConstellationMode = 'path' | 'compare'
type GraphLevel = Exclude<Level, 'person'>

const PANEL_NEIGHBOR_LIMIT = 120

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
    <div className="flex overflow-hidden rounded border border-slate-700/50 bg-black/30 text-[10px] backdrop-blur">
      {(['original', 'cn'] as const).map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={`px-2 py-1 transition-colors ${
            mode === option
              ? 'bg-cyan-900/50 text-cyan-200'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          {option === 'original' ? '原名' : '简中'}
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
    <div className="flex overflow-hidden rounded border border-slate-700/50 bg-black/30 text-[10px] backdrop-blur">
      {GRAPH_LEVELS.map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={`px-2 py-1 transition-colors ${
            level === option
              ? 'bg-slate-700/70 text-slate-100'
              : 'text-slate-500 hover:text-slate-300'
          }`}
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

export default function App() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [level, setLevel] = useState<Level>('global')
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [route, setRoute] = useState<AppRoute>(readRoute)
  const [view, setView] = useState<ViewMode>(() => route.view)
  const [personNameMode, setPersonNameMode] = useState<PersonNameMode>(getInitialPersonNameMode)

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
          const data = await loadPersonGalaxy(route.personId)
          if (cancelled) return
          setGraph(buildGraph(data, 'person'))
          setLevel('person')
          setSelectedNode(route.personId)
        } catch {
          if (cancelled) return
          const data = await loadLevel('global')
          if (cancelled) return
          setGraph(buildGraph(data, 'global'))
          setLevel('global')
          setSelectedNode(null)
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
      setLoading(false)
    }

    void applyRoute()
    return () => { cancelled = true }
  }, [route])

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
      .slice(0, PANEL_NEIGHBOR_LIMIT)
    : []

  const selectedNodeNeighborTotal = selectedNode && graph?.hasNode(selectedNode)
    ? graph.neighbors(selectedNode).length
    : 0

  if (view === 'constellation') {
    return (
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
        <CosmosGalaxyView
          graph={graph}
          onNodeClick={handleNodeClick}
          level={level}
          selectedNode={selectedNode}
          personNameMode={personNameMode}
          onBackToGlobal={() => loadGraphLevelView('global')}
        />
      )}

      <div className="absolute top-4 left-4 right-4 flex items-center gap-3 z-30 pointer-events-none">
        <div className="text-sm font-medium text-slate-400 tracking-widest uppercase">
          Staff Galaxy
        </div>
        <div className="pointer-events-auto">
          <SearchBar onSelect={handleSearchSelect} personNameMode={personNameMode} />
        </div>
        <div className="pointer-events-auto">
          <button
            type="button"
            onClick={openConstellation}
            className="text-xs px-2 py-1 rounded border border-slate-700/50 bg-black/30 text-slate-400 hover:text-cyan-300 hover:border-cyan-600/40 transition-colors"
          >
            关系星图
          </button>
        </div>
        <div className="pointer-events-auto ml-auto">
          <GraphLevelToggle level={level} onChange={handleGraphLevelChange} />
        </div>
        <div className="text-xs text-slate-500 tracking-wider px-2 py-0.5 rounded border border-slate-700/50 bg-black/30 backdrop-blur">
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
          personNameMode={personNameMode}
          onPersonNameModeChange={setPersonNameMode}
          onClose={() => setSelectedNode(null)}
          onNodeClick={handleNodeClick}
          onCompare={handleCompareCollaborator}
        />
      )}
    </div>
  )
}
