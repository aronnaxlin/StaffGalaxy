import { useState, useEffect, useCallback, useRef } from 'react'
import Graph from 'graphology'
import { loadLevel, loadPersonGalaxy, loadSearchIndex, type Level } from './data/loader'
import { buildGraph, swapGraph } from './data/graphBuilder'
import { GalaxyView } from './components/GalaxyView'
import { CosmosGalaxyView } from './components/CosmosGalaxyView'
import { SearchBar } from './components/SearchBar'
import { NodePanel } from './components/NodePanel'
import type { SearchEntry } from './types'

const PANEL_NEIGHBOR_LIMIT = 120
const DEFAULT_PERSON_ID = '94'
type RendererMode = 'sigma' | 'cosmos'

function initialRendererMode(): RendererMode {
  return new URLSearchParams(window.location.search).get('renderer') === 'cosmos'
    ? 'cosmos'
    : 'sigma'
}

function initialGraphLevel(mode: RendererMode): Level {
  return mode === 'cosmos' ? 'person' : 'l0'
}

async function loadGraphData(level: Level, personId = DEFAULT_PERSON_ID) {
  return level === 'person' ? loadPersonGalaxy(personId) : loadLevel(level)
}

export default function App() {
  const [initialMode] = useState<RendererMode>(initialRendererMode)
  const [graph, setGraph] = useState<Graph | null>(null)
  const [level, setLevel] = useState<Level>(() => initialGraphLevel(initialMode))
  const [rendererMode, setRendererMode] = useState<RendererMode>(initialMode)
  const [searchEntries, setSearchEntries] = useState<SearchEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const navigateToNodeRef = useRef<((nodeId: string) => void) | null>(null)

  useEffect(() => {
    const firstLevel = initialGraphLevel(initialMode)
    Promise.all([loadGraphData(firstLevel), loadSearchIndex()]).then(([data, index]) => {
      setGraph(buildGraph(data, firstLevel))
      setLevel(firstLevel)
      if (firstLevel === 'person') setSelectedNode(DEFAULT_PERSON_ID)
      setSearchEntries(index)
      setLoading(false)

      window.setTimeout(() => {
        void loadLevel('l1').catch(() => undefined)
      }, 500)
    })
  }, [initialMode])

  const loadPersonView = useCallback(async (personId: string) => {
    if (!graph) return
    const data = await loadPersonGalaxy(personId)
    swapGraph(graph, data, 'person')
    setLevel('person')
    setSelectedNode(personId)
  }, [graph])

  const handleNodeClick = useCallback((nodeId: string) => {
    if (rendererMode === 'cosmos') {
      void loadPersonView(nodeId)
      return
    }
    setSelectedNode(prev => (prev === nodeId ? null : nodeId))
  }, [loadPersonView, rendererMode])

  const handleSearchSelect = useCallback((id: string) => {
    if (rendererMode === 'cosmos') {
      void loadPersonView(id)
      return
    }
    setSelectedNode(id)
    navigateToNodeRef.current?.(id)
  }, [loadPersonView, rendererMode])

  const handleRendererModeChange = useCallback(async (mode: RendererMode) => {
    setRendererMode(mode)
    const url = new URL(window.location.href)
    if (mode === 'cosmos') url.searchParams.set('renderer', 'cosmos')
    else url.searchParams.delete('renderer')
    window.history.replaceState(null, '', url)

    if (!graph) return
    const nextLevel = initialGraphLevel(mode)
    const data = await loadGraphData(nextLevel)
    swapGraph(graph, data, nextLevel)
    setLevel(nextLevel)
    setSelectedNode(nextLevel === 'person' ? DEFAULT_PERSON_ID : null)
  }, [graph])

  const selectedNodeAttrs = selectedNode && graph?.hasNode(selectedNode)
    ? graph.getNodeAttributes(selectedNode)
    : null

  const selectedNodeNeighbors = selectedNode && graph?.hasNode(selectedNode)
    ? graph.neighbors(selectedNode)
      .map(id => {
        const edge = graph.edge(selectedNode, id)
        return {
          id,
          attrs: graph.getNodeAttributes(id),
          sharedWorksCount: edge ? Number(graph.getEdgeAttribute(edge, 'sharedWorksCount') ?? 0) : 0,
        }
      })
      .sort((a, b) => b.sharedWorksCount - a.sharedWorksCount)
      .slice(0, PANEL_NEIGHBOR_LIMIT)
    : []

  const selectedNodeNeighborTotal = selectedNode && graph?.hasNode(selectedNode)
    ? graph.neighbors(selectedNode).length
    : 0

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
        rendererMode === 'cosmos'
          ? (
            <CosmosGalaxyView
              graph={graph}
              onNodeClick={handleNodeClick}
              navigateToNodeRef={navigateToNodeRef}
              level={level}
              onLevelChange={setLevel}
              selectedNode={selectedNode}
            />
          )
          : (
            <GalaxyView
              graph={graph}
              onNodeClick={handleNodeClick}
              navigateToNodeRef={navigateToNodeRef}
              level={level}
              onLevelChange={setLevel}
              selectedNode={selectedNode}
            />
          )
      )}

      <div className="absolute top-4 left-4 right-4 flex items-center gap-3 z-30 pointer-events-none">
        <div className="text-sm font-medium text-slate-400 tracking-widest uppercase">
          Staff Galaxy
        </div>
        <div className="pointer-events-auto">
          <SearchBar entries={searchEntries} onSelect={handleSearchSelect} />
        </div>
        <div className="pointer-events-auto flex items-center rounded border border-slate-700/70 bg-black/35 p-1 text-xs text-slate-400 backdrop-blur">
          <button
            type="button"
            onClick={() => handleRendererModeChange('sigma')}
            className={`px-2 py-1 ${rendererMode === 'sigma' ? 'bg-slate-700 text-slate-100' : 'hover:text-slate-200'}`}
          >
            Sigma
          </button>
          <button
            type="button"
            onClick={() => handleRendererModeChange('cosmos')}
            className={`px-2 py-1 ${rendererMode === 'cosmos' ? 'bg-cyan-800/80 text-cyan-100' : 'hover:text-slate-200'}`}
          >
            Cosmos
          </button>
        </div>
        <div className="text-xs text-slate-600 tracking-wider ml-auto">
          {level === 'person' ? '个人星系' : level === 'global' ? '全量星系' : level === 'l0' ? '核心视图' : '细节视图'}
        </div>
      </div>

      {selectedNode && selectedNodeAttrs && (
        <NodePanel
          nodeId={selectedNode}
          nodeAttrs={selectedNodeAttrs}
          neighbors={selectedNodeNeighbors}
          neighborTotal={selectedNodeNeighborTotal}
          onClose={() => setSelectedNode(null)}
          onNodeClick={handleNodeClick}
        />
      )}
    </div>
  )
}
