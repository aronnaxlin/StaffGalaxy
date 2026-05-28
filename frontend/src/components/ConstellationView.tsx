import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { loadCollaborationDetail, loadPersonSearchEntry, loadShortestPath } from '../data/loader'
import { personUrl, subjectUrl } from '../data/links'
import { displayPersonName } from '../data/personNames'
import type { SearchEntry, PathResult, CollaborationDetail, PersonNameMode } from '../types'
import { SearchBar } from './SearchBar'

interface ConstellationViewProps {
  mode: 'path' | 'compare'
  initialPersonAId?: string
  initialPersonBId?: string
  onNodeClick: (id: string) => void
  onRouteChange?: (personAId: string | null, personBId: string | null) => void
  personNameMode: PersonNameMode
  onPersonNameModeChange: (mode: PersonNameMode) => void
  onBack: () => void
}

const PATH_COLORS = [
  { stroke: '#fbbf24', glow: 'rgba(251,191,36,0.3)' },
  { stroke: '#22d3ee', glow: 'rgba(34,211,238,0.3)' },
  { stroke: '#c084fc', glow: 'rgba(192,132,252,0.3)' },
  { stroke: '#fb7185', glow: 'rgba(251,113,133,0.3)' },
  { stroke: '#34d399', glow: 'rgba(52,211,153,0.3)' },
]

interface LayoutPoint {
  x: number
  y: number
  id: string
  name: string
  depth: number
}

function workTitle(work: CollaborationDetail['sharedWorks'][number]) {
  return work.subjectNameCn || work.subjectName
}

function snapshotLabel(detail: CollaborationDetail) {
  const snapshot = detail.source.snapshot
  if (!snapshot) return 'snapshot unknown'
  const created = snapshot.archiveCreatedAt ? snapshot.archiveCreatedAt.slice(0, 10) : 'date unknown'
  return `${snapshot.archiveName} · ${created}`
}

function PathStepEvidence({
  detail,
  loading,
  error,
  personNameMode,
}: {
  detail: CollaborationDetail | null
  loading: boolean
  error: string | null
  personNameMode: PersonNameMode
}) {
  if (loading) {
    return (
      <div className="mt-1 rounded border border-slate-800/70 bg-slate-950/60 px-2 py-1 text-[10px] text-slate-500">
        证据加载中…
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-1 rounded border border-red-900/50 bg-red-950/20 px-2 py-1 text-[10px] text-red-300">
        {error}
      </div>
    )
  }

  if (!detail) return null

  return (
    <div className="mt-1 rounded border border-slate-800/70 bg-slate-950/70 p-2">
      <div className="mb-1 text-[10px] text-slate-500">
        {detail.sharedWorksCount} 部共同作品 · score {detail.collaborationScore.toFixed(1)}
      </div>
      <div className="mb-1 text-[10px] text-slate-700 truncate">
        数据快照：{snapshotLabel(detail)}
      </div>
      <ul className="space-y-1 max-h-36 overflow-y-auto pr-1">
        {detail.sharedWorks.slice(0, 6).map(work => (
          <li key={work.subjectId} className="text-[10px] leading-relaxed">
            <div>
              <a
                href={subjectUrl(work.subjectId)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-300 hover:text-cyan-300 transition-colors"
                title={`Bangumi subject #${work.subjectId}`}
              >
                {workTitle(work)}
              </a>
              {work.year && <span className="ml-1 text-slate-600">{work.year}</span>}
            </div>
            <div className="text-slate-600 truncate">
              {displayPersonName(detail.personA, personNameMode)}: {work.personARoles || '—'}
            </div>
            <div className="text-slate-600 truncate">
              {displayPersonName(detail.personB, personNameMode)}: {work.personBRoles || '—'}
            </div>
          </li>
        ))}
      </ul>
      {detail.sharedWorks.length > 6 && (
        <div className="mt-1 text-[10px] text-slate-600">
          仅显示前 6 部；完整证据仍由合作详情接口返回。
        </div>
      )}
    </div>
  )
}

function buildLayout(
  people: { id: string; name: string }[],
  paths: { nodes: string[] }[],
  degree: number,
  aId: string,
  bId: string,
  personNameMode: PersonNameMode,
): LayoutPoint[] {
  // Assign each person to a depth column
  const depthMap = new Map<string, number>()
  depthMap.set(aId, 0)
  depthMap.set(bId, degree)

  for (const path of paths) {
    path.nodes.forEach((nodeId, idx) => {
      const existing = depthMap.get(nodeId)
      if (existing === undefined || idx < existing) {
        depthMap.set(nodeId, idx)
      }
    })
  }

  // Group by depth
  const byDepth = new Map<number, string[]>()
  for (const [nodeId, d] of depthMap) {
    const list = byDepth.get(d) ?? []
    list.push(nodeId)
    byDepth.set(d, list)
  }

  // Layout params
  const marginX = 8
  const marginY = 10
  const usableX = 100 - marginX * 2
  const usableY = 100 - marginY * 2

  const points: LayoutPoint[] = []
  const nameById = new Map(people.map(p => [p.id, displayPersonName(p, personNameMode)]))

  for (let d = 0; d <= degree; d++) {
    const ids = byDepth.get(d) ?? []
    const colX = marginX + (d / degree) * usableX
    const n = ids.length

    ids.forEach((nodeId, i) => {
      const colY = n === 1
        ? 50
        : marginY + ((i + 0.5) / n) * usableY
      points.push({
        x: colX,
        y: colY,
        id: nodeId,
        name: nameById.get(nodeId) ?? nodeId,
        depth: d,
      })
    })
  }

  return points
}

export function ConstellationView({
  mode,
  initialPersonAId,
  initialPersonBId,
  onNodeClick,
  onRouteChange,
  personNameMode,
  onPersonNameModeChange,
  onBack,
}: ConstellationViewProps) {
  const [personA, setPersonA] = useState<SearchEntry | null>(null)
  const [personB, setPersonB] = useState<SearchEntry | null>(null)
  const [result, setResult] = useState<PathResult | null>(null)
  const [directDetail, setDirectDetail] = useState<CollaborationDetail | null>(null)
  const [directChecked, setDirectChecked] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [highlightPath, setHighlightPath] = useState<number | null>(null)
  const [expandedStepKey, setExpandedStepKey] = useState<string | null>(null)
  const [stepDetail, setStepDetail] = useState<CollaborationDetail | null>(null)
  const [stepLoading, setStepLoading] = useState(false)
  const [stepError, setStepError] = useState<string | null>(null)
  const activeStepKeyRef = useRef<string | null>(null)
  const autoFindKeyRef = useRef<string | null>(null)
  const isCompareMode = mode === 'compare'

  const points = useMemo(() => {
    if (!result?.found || !result.people || !result.paths) return []
    return buildLayout(
      result.people,
      result.paths,
      result.degree!,
      personA?.id ?? '',
      personB?.id ?? '',
      personNameMode,
    )
  }, [result, personA, personB, personNameMode])

  const peopleById = useMemo(
    () => new Map(result?.people?.map(p => [p.id, displayPersonName(p, personNameMode)]) ?? []),
    [result, personNameMode],
  )

  const pointMap = useMemo(() => {
    const m = new Map<string, LayoutPoint>()
    points.forEach(p => m.set(p.id, p))
    return m
  }, [points])

  useEffect(() => {
    let cancelled = false

    async function loadInitialPeople() {
      const [initialA, initialB] = await Promise.all([
        initialPersonAId ? loadPersonSearchEntry(initialPersonAId) : Promise.resolve(null),
        initialPersonBId ? loadPersonSearchEntry(initialPersonBId) : Promise.resolve(null),
      ])
      if (cancelled) return
      if (initialA) setPersonA(initialA)
      if (initialB) setPersonB(initialB)
    }

    void loadInitialPeople()
    return () => { cancelled = true }
  }, [initialPersonAId, initialPersonBId])

  const handleFind = useCallback(async () => {
    if (!personA || !personB) return
    onRouteChange?.(personA.id, personB.id)
    setLoading(true)
    setError(null)
    setResult(null)
    setDirectDetail(null)
    setDirectChecked(false)
    setHighlightPath(null)
    setExpandedStepKey(null)
    activeStepKeyRef.current = null
    setStepDetail(null)
    setStepError(null)
    try {
      const data = await loadShortestPath(personA.id, personB.id)
      setResult(data)
      if (!data.found) {
        setError(data.reason ?? '未找到路径')
      } else if (data.degree === 1) {
        setDirectDetail(await loadCollaborationDetail(personA.id, personB.id))
      }
      setDirectChecked(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }, [onRouteChange, personA, personB])

  const clearResult = useCallback(() => {
    setResult(null)
    setDirectDetail(null)
    setDirectChecked(false)
    setError(null)
    setHighlightPath(null)
    setExpandedStepKey(null)
    activeStepKeyRef.current = null
    setStepDetail(null)
    setStepError(null)
  }, [])

  useEffect(() => {
    if (!initialPersonAId || !initialPersonBId) return
    if (personA?.id !== initialPersonAId || personB?.id !== initialPersonBId) return

    const key = `${initialPersonAId}|${initialPersonBId}`
    if (autoFindKeyRef.current === key) return
    autoFindKeyRef.current = key
    void handleFind()
  }, [handleFind, initialPersonAId, initialPersonBId, personA, personB])

  const handleToggleStep = useCallback(async (
    key: string,
    source: string,
    target: string,
  ) => {
    if (expandedStepKey === key) {
      setExpandedStepKey(null)
      activeStepKeyRef.current = null
      setStepDetail(null)
      setStepError(null)
      return
    }

    setExpandedStepKey(key)
    activeStepKeyRef.current = key
    setStepDetail(null)
    setStepError(null)
    setStepLoading(true)
    try {
      const detail = await loadCollaborationDetail(source, target)
      if (activeStepKeyRef.current === key) {
        setStepDetail(detail)
      }
    } catch (e) {
      if (activeStepKeyRef.current === key) {
        setStepError(e instanceof Error ? e.message : '证据请求失败')
      }
    } finally {
      if (activeStepKeyRef.current === key) {
        setStepLoading(false)
      }
    }
  }, [expandedStepKey])

  return (
    <div className="w-full h-full bg-[#080810] flex overflow-hidden">
      {/* Left: search sidebar */}
      <div className="w-72 shrink-0 border-r border-slate-800/50 bg-black/30 flex flex-col p-4 gap-3 z-20">
        <button
          onClick={onBack}
          className="text-xs px-3 py-1.5 rounded border border-slate-700/50 text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-colors w-fit"
        >
          ← 返回星系
        </button>

        <div className="text-xs font-medium text-slate-400 tracking-wider uppercase">
          {isCompareMode ? '双人比较' : '关系星图'}
        </div>
        <div className="flex w-fit overflow-hidden rounded border border-slate-700/50 text-[10px]">
          {(['original', 'cn'] as const).map(mode => (
            <button
              key={mode}
              type="button"
              onClick={() => onPersonNameModeChange(mode)}
              className={`px-2 py-1 transition-colors ${
                personNameMode === mode
                  ? 'bg-cyan-900/50 text-cyan-200'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {mode === 'original' ? '原名' : '简中'}
            </button>
          ))}
        </div>

        <div className="space-y-2">
          <div>
            <div className="text-[10px] text-slate-500 mb-1">起点</div>
            <SearchBar
              onSelect={(entry) => { setPersonA(entry); clearResult() }}
              selectedEntry={personA}
              onClear={() => { setPersonA(null); clearResult() }}
              personNameMode={personNameMode}
            />
          </div>
          <div className="text-center text-slate-600 text-xs">
            {isCompareMode ? '↓ 比较 ↓' : '↓ 连接到 ↓'}
          </div>
          <div>
            <div className="text-[10px] text-slate-500 mb-1">终点</div>
            <SearchBar
              onSelect={(entry) => { setPersonB(entry); clearResult() }}
              selectedEntry={personB}
              onClear={() => { setPersonB(null); clearResult() }}
              personNameMode={personNameMode}
            />
          </div>
        </div>

        <button
          type="button"
          disabled={!personA || !personB || loading}
          onClick={() => void handleFind()}
          className="w-full py-1.5 rounded-lg text-xs font-medium transition-colors
            disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed
            bg-cyan-900/50 text-cyan-200 hover:bg-cyan-800/60 border border-cyan-600/30"
        >
          {loading ? '探寻中…' : isCompareMode ? '比较合作与路径' : '探寻路径'}
        </button>

        {error && (
          <div className="text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded px-2 py-1.5">
            {error}
          </div>
        )}

        {directChecked && personA && personB && (
          <div className="mt-1 rounded-lg border border-slate-800/70 bg-slate-950/70 p-3">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">
                {isCompareMode ? '直接合作比较' : '直接合作'}
              </div>
              {directDetail && (
                <div className="text-[10px] text-cyan-300 tabular-nums">
                  {directDetail.sharedWorksCount} 部 · {directDetail.firstYear}
                  {directDetail.lastYear && directDetail.lastYear !== directDetail.firstYear
                    ? `–${directDetail.lastYear}`
                    : ''}
                </div>
              )}
            </div>

            {directDetail ? (
              <div className="space-y-2">
                <div className="text-[11px] text-slate-400">
                  score {directDetail.collaborationScore.toFixed(1)} · 来自完整合作查询
                </div>
                <div className="text-[10px] text-slate-700 truncate">
                  数据快照：{snapshotLabel(directDetail)}
                </div>
                <ul className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  {directDetail.sharedWorks.slice(0, 8).map(work => (
                    <li key={work.subjectId} className="text-[11px] leading-relaxed">
                      <div>
                        <a
                          href={subjectUrl(work.subjectId)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-300 hover:text-cyan-300 transition-colors"
                          title={`Bangumi subject #${work.subjectId}`}
                        >
                          {workTitle(work)}
                        </a>
                        {work.year && (
                          <span className="ml-1 text-slate-600">{work.year}</span>
                        )}
                      </div>
                      <div className="text-slate-600 truncate">
                        {displayPersonName(personA, personNameMode)}: {work.personARoles || '—'}
                      </div>
                      <div className="text-slate-600 truncate">
                        {displayPersonName(personB, personNameMode)}: {work.personBRoles || '—'}
                      </div>
                    </li>
                  ))}
                </ul>
                {directDetail.sharedWorks.length > 8 && (
                  <div className="text-[10px] text-slate-600">
                    仅显示前 8 部，完整列表可在人物详情中展开。
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-500 leading-relaxed">
                未找到直接合作证据；{isCompareMode ? '已继续查询两人的最短连接路径。' : '下方展示基于完整合作图的最短连接路径。'}
              </div>
            )}
          </div>
        )}

        {/* Path legend */}
        {result?.found && result.paths && (
          <div className="mt-2 space-y-1.5">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider">
              {result.degree === 1 ? '直接合作' : `${result.degree} 度分隔`} · {result.pathCount} 条路径
            </div>
            {result.paths.map((path, i) => {
              const colors = PATH_COLORS[i % PATH_COLORS.length]
              return (
                <div
                  key={i}
                  className={`rounded border border-transparent px-1 py-1 transition-opacity ${
                    highlightPath === null || highlightPath === i ? 'opacity-100' : 'opacity-30'
                  }`}
                  onMouseEnter={() => setHighlightPath(i)}
                  onMouseLeave={() => setHighlightPath(null)}
                >
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: colors.stroke }} />
                    <span className="text-slate-500 leading-tight">
                      {path.nodes.map((id, index) => (
                        <span key={id}>
                          {index > 0 && <span className="mx-1 text-slate-700">→</span>}
                          <a
                            href={personUrl(id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-cyan-300 transition-colors"
                            title={`Bangumi person #${id}`}
                          >
                            {peopleById.get(id) ?? id}
                          </a>
                        </span>
                      ))}
                    </span>
                  </div>

                  <div className="mt-1 ml-4 space-y-1">
                    {path.steps.map((step, stepIdx) => {
                      const key = `${i}:${stepIdx}:${step.source}:${step.target}`
                      const expanded = expandedStepKey === key
                      return (
                        <div key={key}>
                          <button
                            type="button"
                            onClick={() => void handleToggleStep(key, step.source, step.target)}
                            className={`w-full rounded px-1.5 py-1 text-left text-[10px] transition-colors ${
                              expanded
                                ? 'bg-cyan-950/30 text-cyan-200'
                                : 'text-slate-500 hover:bg-slate-900/70 hover:text-slate-300'
                            }`}
                          >
                            {expanded ? '收起证据' : '展开证据'} · {peopleById.get(step.source) ?? step.source}
                            <span className="mx-1 text-slate-700">→</span>
                            {peopleById.get(step.target) ?? step.target}
                            <span className="ml-1 text-slate-600">
                              {step.sharedWorksCount} 部 · {step.collaborationScore.toFixed(1)}
                            </span>
                          </button>
                          {expanded && (
                            <PathStepEvidence
                              detail={stepDetail}
                              loading={stepLoading}
                              error={stepError}
                              personNameMode={personNameMode}
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Right: constellation canvas */}
      <div className="flex-1 relative">
        <svg
          className="w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Path edges */}
          {result?.found && result.paths?.map((path, pathIdx) => {
            const isHighlighted = highlightPath === null || highlightPath === pathIdx
            const colors = PATH_COLORS[pathIdx % PATH_COLORS.length]
            const nodeIds = path.nodes

            return (
              <g key={pathIdx} opacity={isHighlighted ? 1 : 0.12}>
                {nodeIds.slice(0, -1).map((nodeId, i) => {
                  const from = pointMap.get(nodeId)
                  const to = pointMap.get(nodeIds[i + 1])
                  if (!from || !to) return null
                  const step = path.steps[i]
                  const midX = (from.x + to.x) / 2
                  const midY = (from.y + to.y) / 2
                  const curvature = 0.2 + pathIdx * 0.06

                  return (
                    <g key={`${nodeId}-${nodeIds[i + 1]}`}>
                      {/* Glow */}
                      <path
                        d={`M${from.x},${from.y} Q${from.x + (to.x - from.x) * curvature},${from.y + (to.y - from.y) * 0.15} ${midX},${midY} T${to.x},${to.y}`}
                        fill="none"
                        stroke={colors.glow}
                        strokeWidth={1.8}
                        strokeLinecap="round"
                      />
                      {/* Line */}
                      <path
                        d={`M${from.x},${from.y} Q${from.x + (to.x - from.x) * curvature},${from.y + (to.y - from.y) * 0.15} ${midX},${midY} T${to.x},${to.y}`}
                        fill="none"
                        stroke={colors.stroke}
                        strokeWidth={0.8}
                        strokeLinecap="round"
                      />
                      {/* Edge label */}
                      {step && (
                        <text
                          x={midX}
                          y={midY - 2.5}
                          fill={colors.stroke}
                          fontSize="2.2"
                          textAnchor="middle"
                          opacity={isHighlighted ? 0.85 : 0}
                        >
                          {step.sharedWorksCount}部
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
            )
          })}

          {/* Nodes */}
          {points.map((point) => {
            const isEndpoint = point.depth === 0 || (result?.degree !== undefined && point.depth === result.degree)
            const r = isEndpoint ? 2.2 : 1.6

            return (
              <g
                key={point.id}
                className="cursor-pointer"
                onClick={() => onNodeClick(point.id)}
              >
                {/* Glow ring */}
                <circle cx={point.x} cy={point.y} r={r * 2.2}
                  fill={isEndpoint ? '#fbbf24' : '#e2e8f0'}
                  opacity={0.06}
                />
                <circle cx={point.x} cy={point.y} r={r * 1.4}
                  fill={isEndpoint ? '#fbbf24' : '#e2e8f0'}
                  opacity={0.12}
                />
                {/* Core */}
                <circle cx={point.x} cy={point.y} r={r}
                  fill={isEndpoint ? '#fbbf24' : '#cbd5e1'}
                />
                {/* Invisible larger hit area */}
                <circle cx={point.x} cy={point.y} r={r * 3}
                  fill="transparent"
                />
                {/* Label */}
                <text
                  x={point.x}
                  y={point.y + r * 2.5 + 2}
                  fill={isEndpoint ? '#fbbf24' : '#94a3b8'}
                  fontSize={isEndpoint ? 2.8 : 2.4}
                  textAnchor="middle"
                  fontWeight={isEndpoint ? 600 : 400}
                >
                  {point.name}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
