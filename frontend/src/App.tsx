import { useState, useEffect, useCallback, useRef } from 'react'
import Graph from 'graphology'
import { loadLevel, loadSearchIndex, type Level } from './data/loader'
import { buildGraph } from './data/graphBuilder'
import { GalaxyView } from './components/GalaxyView'
import { SearchBar } from './components/SearchBar'
import { NodePanel } from './components/NodePanel'
import type { SearchEntry } from './types'

const PANEL_NEIGHBOR_LIMIT = 120

export default function App() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [level, setLevel] = useState<Level>('l0')
  const [searchEntries, setSearchEntries] = useState<SearchEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const navigateToNodeRef = useRef<((nodeId: string) => void) | null>(null)

  useEffect(() => {
    Promise.all([loadLevel('l0'), loadSearchIndex()]).then(([data, index]) => {
      setGraph(buildGraph(data, 'l0'))
      setSearchEntries(index)
      setLoading(false)

      window.setTimeout(() => {
        void loadLevel('l1').catch(() => undefined)
      }, 500)
    })
  }, [])

  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNode(prev => (prev === nodeId ? null : nodeId))
  }, [])

  const handleSearchSelect = useCallback((id: string) => {
    setSelectedNode(id)
    navigateToNodeRef.current?.(id)
  }, [])

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
        <GalaxyView
          graph={graph}
          onNodeClick={handleNodeClick}
          navigateToNodeRef={navigateToNodeRef}
          level={level}
          onLevelChange={setLevel}
          selectedNode={selectedNode}
        />
      )}

      <div className="absolute top-4 left-4 right-4 flex items-center gap-3 z-30 pointer-events-none">
        <div className="text-sm font-medium text-slate-400 tracking-widest uppercase">
          Staff Galaxy
        </div>
        <div className="pointer-events-auto">
          <SearchBar entries={searchEntries} onSelect={handleSearchSelect} />
        </div>
        <div className="text-xs text-slate-600 tracking-wider ml-auto">
          {level === 'l0' ? '全局视图' : '细节视图'}
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
