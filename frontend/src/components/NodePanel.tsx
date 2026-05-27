interface NodePanelProps {
  nodeId: string
  nodeAttrs: Record<string, unknown>
  neighbors: Array<{ id: string; attrs: Record<string, unknown> }>
  neighborTotal: number
  onClose: () => void
  onNodeClick: (id: string) => void
}

export function NodePanel({ nodeId, nodeAttrs, neighbors, neighborTotal, onClose, onNodeClick }: NodePanelProps) {
  const name = nodeAttrs.name as string
  const degree = nodeAttrs.degree as number

  return (
    <div className="absolute right-4 top-16 w-72 bg-slate-950/90 border border-slate-800 rounded-xl shadow-2xl backdrop-blur p-4 z-40">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-base font-medium text-slate-100">{name}</div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 text-lg leading-none ml-2"
        >
          ×
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <span className="text-xs px-2 py-0.5 rounded border border-slate-700 text-slate-400">
          {degree} 合作
        </span>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
        <span>直接合作者</span>
        {neighborTotal > neighbors.length && (
          <span>显示前 {neighbors.length} / {neighborTotal}</span>
        )}
      </div>
      <ul className="space-y-1 max-h-48 overflow-y-auto">
        {neighbors.map(({ id, attrs }) => (
          <li key={id}>
            <button
              className="w-full text-left text-sm text-slate-300 hover:text-violet-300 py-0.5 truncate"
              onClick={() => onNodeClick(id)}
            >
              {attrs.name as string}
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-4 pt-3 border-t border-slate-800">
        <a
          href={`https://bgm.tv/person/${nodeId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 hover:text-violet-400"
        >
          Bangumi 页面 →
        </a>
      </div>
    </div>
  )
}
