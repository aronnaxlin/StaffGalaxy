import { useState, useCallback, useEffect, useMemo } from 'react'
import { loadCollaborationDetail, loadPersonCredits, loadPersonDetail } from '../data/loader'
import { personUrl, subjectUrl } from '../data/links'
import {
  displayPersonName,
  displaySubjectName,
  secondaryPersonName,
  secondarySubjectName,
} from '../data/personNames'
import type { CollaborationDetail, PersonCredit, PersonCreditsResponse, PersonDetail, PersonNameMode } from '../types'
import {
  dividerClass,
  mutedLink,
  panelShell,
  panelSoft,
  sectionLabel,
  segmentedButtonClass,
  segmentedGroupClass,
  smallPillClass,
  subtleLink,
} from './ui'

interface NeighborInfo {
  id: string
  attrs: Record<string, unknown>
  sharedWorksCount: number
  collaborationScore: number
  firstYear?: number
  lastYear?: number
}

interface NodePanelProps {
  nodeId: string
  nodeAttrs: Record<string, unknown>
  neighbors: NeighborInfo[]
  neighborTotal: number
  neighborLimit: number
  neighborMinShared: number
  onNeighborLimitChange: (limit: number) => void
  onNeighborMinSharedChange: (minShared: number) => void
  personNameMode: PersonNameMode
  onClose: () => void
  onNodeClick: (id: string) => void
  onCompare: (personAId: string, personBId: string) => void
  expandedNeighborId: string | null
  expandingNeighborId: string | null
  onToggleNeighborExpansion: (neighborId: string) => void
}

type NeighborRoleFilter = 'all' | 'sab' | 'cd' | 'ef'
type NeighborTimeFilter = 'all' | 'recent10' | 'since2010' | 'since2000'

const NEIGHBOR_LIMIT_OPTIONS = [60, 120, 240] as const
const NEIGHBOR_MIN_SHARED_OPTIONS = [1, 3, 5, 10] as const
const ROLE_FILTERS: { value: NeighborRoleFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'sab', label: 'SAB' },
  { value: 'cd', label: 'CD' },
  { value: 'ef', label: 'EF' },
]
const TIME_FILTERS: { value: NeighborTimeFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'recent10', label: '近10年' },
  { value: 'since2010', label: '2010+' },
  { value: 'since2000', label: '2000+' },
]

function yearRange(first: number | null, latest: number | null) {
  if (!first && !latest) return null
  if (first && latest && first !== latest) return `${first}–${latest}`
  return String(first ?? latest)
}

function matchesRoleFilter(neighborRoleTier: unknown, filter: NeighborRoleFilter) {
  if (filter === 'all') return true
  const tier = String(neighborRoleTier ?? '').match(/[SABCDEF]/)?.[0]
  if (!tier) return false
  if (filter === 'sab') return tier === 'S' || tier === 'A' || tier === 'B'
  if (filter === 'cd') return tier === 'C' || tier === 'D'
  return tier === 'E' || tier === 'F'
}

function matchesTimeFilter(lastYear: number | undefined, filter: NeighborTimeFilter) {
  if (filter === 'all') return true
  if (!lastYear) return false
  if (filter === 'recent10') return lastYear >= new Date().getFullYear() - 10
  if (filter === 'since2010') return lastYear >= 2010
  return lastYear >= 2000
}

function snapshotLabel(detail: PersonDetail | PersonCreditsResponse | CollaborationDetail | null) {
  const snapshot = detail?.source.snapshot
  if (!snapshot) return 'snapshot unknown'
  const created = snapshot.archiveCreatedAt ? snapshot.archiveCreatedAt.slice(0, 10) : 'date unknown'
  return `${snapshot.archiveName} · ${created}`
}

function PersonSummary({
  detail,
  loading,
  open,
  nameMode,
  onToggle,
}: {
  detail: PersonDetail | null
  loading: boolean
  open: boolean
  nameMode: PersonNameMode
  onToggle: () => void
}) {
  const range = detail
    ? yearRange(detail.stats.firstCreditYear, detail.stats.latestCreditYear)
    : null

  return (
    <div className={`${panelSoft} mb-3 shrink-0`}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs text-slate-400 transition-colors hover:text-cyan-300"
      >
        <span>人物资料</span>
        <span className="text-[10px] text-slate-600">
          {loading ? '加载中…' : open ? '收起' : '展开'}
        </span>
      </button>

      {open && (
        <div className={`border-t ${dividerClass} p-3`}>
          {loading && <div className="text-xs text-slate-500">人物资料加载中…</div>}

          {!loading && detail && (
            <>
              <div className="mb-2 grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-sm text-slate-200 tabular-nums">{detail.stats.animeSubjectCount}</div>
                  <div className="text-[10px] text-slate-500">参与动画</div>
                </div>
                <div>
                  <div className="text-sm text-slate-200 tabular-nums">{detail.stats.animeCreditCount}</div>
                  <div className="text-[10px] text-slate-500">职位记录</div>
                </div>
                <div>
                  <div className="text-sm text-slate-200 tabular-nums">{range ?? '—'}</div>
                  <div className="text-[10px] text-slate-500">年份范围</div>
                </div>
              </div>

              {detail.topRoles.length > 0 && (
                <div className="mb-2">
                  <div className={`${sectionLabel} mb-1`}>常见职位</div>
                  <div className="flex flex-wrap gap-1">
                    {detail.topRoles.slice(0, 5).map(role => (
                      <span
                        key={`${role.position}-${role.roleTier}`}
                        className={smallPillClass()}
                        title={`${role.normalizedRole} / Tier ${role.roleTier}`}
                      >
                        {role.position} · {role.creditCount}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {detail.recentWorks.length > 0 && (
                <div>
                  <div className={`${sectionLabel} mb-1`}>最近参与</div>
                  <ul className="space-y-1">
                    {detail.recentWorks.slice(0, 4).map(work => (
                      <li key={work.subjectId} className="text-[11px] leading-snug">
                        <a
                          href={subjectUrl(work.subjectId)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={subtleLink}
                          title={`Bangumi subject #${work.subjectId}`}
                        >
                          {displaySubjectName(work, nameMode)}
                        </a>
                        {work.year && <span className="ml-1 text-slate-600">{work.year}</span>}
                        {work.roles && <div className="truncate text-slate-600">{work.roles}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className={`mt-2 truncate border-t ${dividerClass} pt-2 text-[10px] text-slate-700`}>
                {detail.source.label} · {snapshotLabel(detail)}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

interface CreditWorkGroup {
  subjectId: number
  subjectName: string
  subjectNameCn: string
  year: number | null
  credits: PersonCredit[]
}

function groupCreditsByWork(credits: PersonCredit[]): CreditWorkGroup[] {
  const bySubject = new Map<number, CreditWorkGroup>()
  for (const credit of credits) {
    const existing = bySubject.get(credit.subjectId)
    if (existing) {
      existing.credits.push(credit)
    } else {
      bySubject.set(credit.subjectId, {
        subjectId: credit.subjectId,
        subjectName: credit.subjectName,
        subjectNameCn: credit.subjectNameCn,
        year: credit.year,
        credits: [credit],
      })
    }
  }
  return Array.from(bySubject.values())
}

function PersonCreditsHistory({
  credits,
  loading,
  open,
  total,
  nameMode,
  onToggle,
}: {
  credits: PersonCreditsResponse | null
  loading: boolean
  open: boolean
  total: number | null
  nameMode: PersonNameMode
  onToggle: () => void
}) {
  const groups = useMemo(
    () => groupCreditsByWork(credits?.credits ?? []),
    [credits],
  )

  return (
    <div className={`${panelSoft} mb-3 shrink-0`}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs text-slate-400 transition-colors hover:text-cyan-300"
      >
        <span>{open ? '收起完整履历' : '展开完整履历'}</span>
        <span className="text-[10px] text-slate-600">
          {total !== null ? `${total} 条职位记录` : 'Archive credits'}
        </span>
      </button>

      {open && (
        <div className={`border-t ${dividerClass} px-3 py-2`}>
          {loading && (
            <div className="text-xs text-slate-500">完整履历加载中…</div>
          )}

          {!loading && credits && (
            <>
              <div className="mb-2 text-[10px] text-slate-600">
                按作品合并显示，职位保留 Archive 原始记录。
              </div>
              <ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
                {groups.map(group => {
                  const name = displaySubjectName(group, nameMode)
                  return (
                    <li key={group.subjectId} className="text-[11px] leading-relaxed">
                      <div>
                        <a
                          href={subjectUrl(group.subjectId)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={subtleLink}
                          title={`Bangumi subject #${group.subjectId}`}
                        >
                          {name}
                        </a>
                        {group.year && <span className="ml-1 text-slate-600">{group.year}</span>}
                      </div>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {group.credits.map(credit => (
                          <span
                            key={`${group.subjectId}-${credit.positionId}-${credit.rawPosition}-${credit.normalizedRole}`}
                            className="rounded-full border border-slate-800 bg-slate-900/70 px-1.5 py-0.5 text-[10px] text-slate-500"
                            title={`${credit.rawPosition} / ${credit.normalizedRole} / Tier ${credit.roleTier}`}
                          >
                            {credit.rawPosition || credit.position}
                          </span>
                        ))}
                      </div>
                    </li>
                  )
                })}
              </ul>
              {credits.total > credits.credits.length && (
                <div className="mt-2 text-[10px] text-slate-600">
                  已显示前 {credits.credits.length} / {credits.total} 条记录。
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function CollabDetail({
  personA,
  personB,
  detail,
  loading,
  nameMode,
}: {
  personA: string
  personB: string
  detail: CollaborationDetail | null
  loading: boolean
  nameMode: PersonNameMode
}) {
  if (loading) {
    return (
      <div className="ml-6 mt-2 border-l border-slate-700/50 py-1 pl-3 text-xs text-slate-500">
        加载中…
      </div>
    )
  }

  if (!detail) return null

  return (
    <div className="ml-6 mt-1.5 border-l border-cyan-500/30 pl-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-slate-400">
        <span>共 {detail.sharedWorksCount} 部作品</span>
        {detail.firstYear && (
          <span className="text-slate-500">
            {detail.firstYear}{detail.lastYear && detail.lastYear !== detail.firstYear ? `–${detail.lastYear}` : ''}
          </span>
        )}
        <span className="text-slate-600">
          score: {detail.collaborationScore.toFixed(1)}
        </span>
      </div>
      <div className="mb-2 truncate text-[10px] text-slate-700">
        数据快照：{snapshotLabel(detail)}
      </div>
      <ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
        {detail.sharedWorks.map(work => {
          const primary = displaySubjectName(work, nameMode)
          const secondary = secondarySubjectName(work, nameMode)
          return (
            <li key={work.subjectId} className="text-xs leading-relaxed">
              <div className="font-medium">
                <a
                  href={subjectUrl(work.subjectId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={subtleLink}
                  title={`Bangumi subject #${work.subjectId}`}
                >
                  {primary}
                </a>
                {secondary && (
                  <span className="text-slate-500 ml-1">({secondary})</span>
                )}
                {work.year && (
                  <span className="text-slate-600 ml-1">{work.year}</span>
                )}
              </div>
              <div className="flex flex-col gap-0.5 mt-0.5 text-slate-500">
                <div className="flex items-baseline gap-1">
                  <span className="text-[10px] text-slate-600 w-5 shrink-0">{personA.slice(0, 2)}</span>
                  <span>{work.personARoles || '—'}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-[10px] text-cyan-600 w-5 shrink-0">{personB.slice(0, 2)}</span>
                  <span>{work.personBRoles || '—'}</span>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function NodePanel({
  nodeId,
  nodeAttrs,
  neighbors,
  neighborTotal,
  neighborLimit,
  neighborMinShared,
  onNeighborLimitChange,
  onNeighborMinSharedChange,
  personNameMode,
  onClose,
  onNodeClick,
  onCompare,
  expandedNeighborId,
  expandingNeighborId,
  onToggleNeighborExpansion,
}: NodePanelProps) {
  const name = nodeAttrs.name as string
  const nameCn = nodeAttrs.nameCn as string | undefined
  const nameTw = nodeAttrs.nameTw as string | undefined
  const displayName = displayPersonName({ name, nameCn, nameTw }, personNameMode)
  const secondaryName = secondaryPersonName({ name, nameCn, nameTw }, personNameMode)
  const degree = nodeAttrs.degree as number
  const roleLayer = nodeAttrs.roleLayer as string | undefined
  const weightedDegree = nodeAttrs.visibleWeightedDegree as number | undefined
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [collabDetail, setCollabDetail] = useState<CollaborationDetail | null>(null)
  const [collabLoading, setCollabLoading] = useState(false)
  const [personDetail, setPersonDetail] = useState<PersonDetail | null>(null)
  const [personDetailLoading, setPersonDetailLoading] = useState(false)
  const [personCredits, setPersonCredits] = useState<PersonCreditsResponse | null>(null)
  const [personCreditsOpen, setPersonCreditsOpen] = useState(false)
  const [personCreditsLoading, setPersonCreditsLoading] = useState(false)
  const [personSummaryOpen, setPersonSummaryOpen] = useState(false)
  const [neighborRoleFilter, setNeighborRoleFilter] = useState<NeighborRoleFilter>('all')
  const [neighborTimeFilter, setNeighborTimeFilter] = useState<NeighborTimeFilter>('all')

  const filteredNeighbors = useMemo(
    () => neighbors.filter(neighbor => (
      matchesRoleFilter(neighbor.attrs.neighborRoleTier, neighborRoleFilter)
      && matchesTimeFilter(neighbor.lastYear, neighborTimeFilter)
    )),
    [neighborRoleFilter, neighborTimeFilter, neighbors],
  )

  useEffect(() => {
    let cancelled = false
    setPersonDetail(null)
    setPersonDetailLoading(true)
    loadPersonDetail(nodeId)
      .then(detail => {
        if (!cancelled) setPersonDetail(detail)
      })
      .catch(() => {
        if (!cancelled) setPersonDetail(null)
      })
      .finally(() => {
        if (!cancelled) setPersonDetailLoading(false)
      })
    return () => { cancelled = true }
  }, [nodeId])

  useEffect(() => {
    setPersonCredits(null)
    setPersonCreditsOpen(false)
    setPersonCreditsLoading(false)
    setPersonSummaryOpen(false)
  }, [nodeId])

  const handleExpand = useCallback(async (neighborId: string, _neighborName: string) => {
    if (expandedId === neighborId) {
      setExpandedId(null)
      setCollabDetail(null)
      return
    }
    setExpandedId(neighborId)
    setCollabLoading(true)
    setCollabDetail(null)
    try {
      const detail = await loadCollaborationDetail(nodeId, neighborId)
      setCollabDetail(detail)
    } catch {
      setCollabDetail(null)
    } finally {
      setCollabLoading(false)
    }
  }, [expandedId, nodeId])

  const handleToggleCredits = useCallback(async () => {
    if (personCreditsOpen) {
      setPersonCreditsOpen(false)
      return
    }

    setPersonCreditsOpen(true)
    if (personCredits) return

    setPersonCreditsLoading(true)
    try {
      setPersonCredits(await loadPersonCredits(nodeId))
    } catch {
      setPersonCredits(null)
    } finally {
      setPersonCreditsLoading(false)
    }
  }, [nodeId, personCredits, personCreditsOpen])

  return (
    <div className={`${panelShell} absolute right-4 top-16 z-40 flex max-h-[calc(100dvh-6rem)] w-96 flex-col overflow-hidden p-3`}>
      {/* Header */}
      <div className="mb-3 flex shrink-0 items-start justify-between rounded-lg border border-[#f09199]/20 bg-[linear-gradient(135deg,rgba(240,145,153,0.16),rgba(54,156,248,0.08))] p-3">
        <div className="min-w-0">
          <div className="text-base font-semibold text-white truncate">{displayName}</div>
          {secondaryName && (
            <div className="mt-0.5 truncate text-[11px] text-slate-400">{secondaryName}</div>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-slate-300">
              {degree} 位合作者
            </span>
            {weightedDegree !== undefined && (
              <span className={smallPillClass()}>
                w{weightedDegree.toFixed(0)}
              </span>
            )}
            {roleLayer && (
              <span className={smallPillClass()}>
                {roleLayer}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="ml-2 shrink-0 text-lg leading-none text-slate-400 transition-colors hover:text-[#f4a8bc]"
        >
          ×
        </button>
      </div>

      <PersonSummary
        detail={personDetail}
        loading={personDetailLoading}
        open={personSummaryOpen}
        nameMode={personNameMode}
        onToggle={() => setPersonSummaryOpen(value => !value)}
      />

      <PersonCreditsHistory
        credits={personCredits}
        loading={personCreditsLoading}
        open={personCreditsOpen}
        total={personDetail?.stats.animeCreditCount ?? personCredits?.total ?? null}
        nameMode={personNameMode}
        onToggle={() => void handleToggleCredits()}
      />

      <div className={`${panelSoft} mb-3 shrink-0 p-3`}>
        <div className={`${sectionLabel} mb-2`}>合作者筛选</div>
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-slate-500">边强度</span>
            <div className={segmentedGroupClass}>
              {NEIGHBOR_MIN_SHARED_OPTIONS.map(value => (
                <button
                  key={value}
                  type="button"
                  onClick={() => onNeighborMinSharedChange(value)}
                  className={segmentedButtonClass(neighborMinShared === value, 'cyan')}
                  title={`只加载共同作品数 >= ${value} 的一跳合作者`}
                >
                  {value}+
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-slate-500">显示数</span>
            <div className={segmentedGroupClass}>
              {NEIGHBOR_LIMIT_OPTIONS.map(value => (
                <button
                  key={value}
                  type="button"
                  onClick={() => onNeighborLimitChange(value)}
                  className={segmentedButtonClass(neighborLimit === value, 'slate')}
                  title={`加载前 ${value} 位合作者`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-slate-500">合作者职位</span>
            <div className={segmentedGroupClass}>
              {ROLE_FILTERS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setNeighborRoleFilter(option.value)}
                  className={segmentedButtonClass(neighborRoleFilter === option.value, 'pink')}
                  title="按该合作者在共享作品中的最高职位 tier 过滤面板列表"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-slate-500">时间</span>
            <div className={segmentedGroupClass}>
              {TIME_FILTERS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setNeighborTimeFilter(option.value)}
                  className={segmentedButtonClass(neighborTimeFilter === option.value, 'slate')}
                  title="按最后一次共同作品年份过滤面板列表"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Neighbor list header */}
      <div className="mb-2 flex shrink-0 items-center justify-between text-xs text-slate-500">
        <span className={sectionLabel}>按合作次数排序</span>
        {neighborTotal > filteredNeighbors.length && (
          <span>
            {filteredNeighbors.length} / {neighborTotal}
          </span>
        )}
      </div>

      {/* Neighbor list */}
      <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1">
        {filteredNeighbors.length === 0 && (
          <li className="rounded-lg border border-[#f09199]/20 bg-black/20 px-3 py-2 text-xs text-slate-400">
            当前筛选下没有可显示的一跳合作者。
          </li>
        )}
        {filteredNeighbors.map(({ id, attrs, sharedWorksCount, collaborationScore, firstYear, lastYear }) => {
          const isExpanded = expandedId === id
          const isGraphExpanded = expandedNeighborId === id
          const isGraphExpanding = expandingNeighborId === id
          const neighborName = attrs.name as string
          const neighborNameCn = attrs.nameCn as string | undefined
          const neighborNameTw = attrs.nameTw as string | undefined
          const neighborDisplayName = displayPersonName(
            { name: neighborName, nameCn: neighborNameCn, nameTw: neighborNameTw },
            personNameMode,
          )
          const neighborSecondaryName = secondaryPersonName(
            { name: neighborName, nameCn: neighborNameCn, nameTw: neighborNameTw },
            personNameMode,
          )
          return (
            <li key={id}>
              <button
                className="group w-full rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-[#f09199]/15 hover:bg-[#f09199]/10"
                onClick={() => onNodeClick(id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-slate-200 transition-colors group-hover:text-[#d9ecff]">
                      {neighborDisplayName}
                    </span>
                    {neighborSecondaryName && (
                      <span className="block truncate text-[10px] text-slate-600">{neighborSecondaryName}</span>
                    )}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    {firstYear && (
                      <span className="text-[10px] text-slate-600 tabular-nums">
                        {firstYear}{lastYear && lastYear !== firstYear ? `–${String(lastYear).slice(-2)}` : ''}
                      </span>
                    )}
                      <span className="min-w-[1.5rem] rounded-full border border-[#6baae8]/25 bg-[#0f3e75]/35 px-1.5 py-0.5 text-right text-[10px] tabular-nums text-[#b9d8f4]">
                        {sharedWorksCount}
                      </span>
                  </div>
                </div>
                {collaborationScore > 0 && (
                  <div className="flex items-center gap-1 mt-0.5">
                    <div
                      className="h-0.5 rounded-full bg-[#6baae8]/80"
                      style={{
                        width: `${Math.min(100, (collaborationScore / 10) * 8)}%`,
                        maxWidth: '6rem',
                      }}
                    />
                    <span className="text-[10px] text-slate-600">{collaborationScore.toFixed(1)}</span>
                  </div>
                )}
              </button>

              {/* Expand toggle */}
              <button
                className={`w-full rounded px-2 py-0.5 text-left text-[11px] transition-colors ${
                  isExpanded
                    ? 'bg-[#0f3e75]/45 text-[#d9ecff]'
                    : 'text-slate-500 hover:bg-[#6baae8]/10 hover:text-[#b9d8f4]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  void handleExpand(id, neighborName)
                }}
              >
                {isExpanded ? '收起合作详情 ▾' : '展开合作详情 ▸'}
              </button>

              <button
                type="button"
                className={`w-full rounded px-2 py-0.5 text-left text-[11px] transition-colors ${
                  isGraphExpanded
                    ? 'bg-[#0f3e75]/45 text-[#d9ecff]'
                    : 'text-slate-500 hover:bg-[#6baae8]/10 hover:text-[#b9d8f4]'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleNeighborExpansion(id)
                }}
                disabled={Boolean(expandingNeighborId)}
                title="在当前个人星系中临时展开该合作者的一跳邻域"
              >
                {isGraphExpanding
                  ? '二跳邻域加载中…'
                  : isGraphExpanded
                    ? '收起二跳邻域 △'
                    : '展开二跳邻域 +'}
              </button>

              <button
                type="button"
                className="w-full rounded px-2 py-0.5 text-left text-[11px] text-slate-500 transition-colors hover:bg-[#f09199]/10 hover:text-[#f4a8bc]"
                onClick={(e) => {
                  e.stopPropagation()
                  onCompare(nodeId, id)
                }}
              >
                比较两人合作 →
              </button>

              {/* Expanded collaboration detail */}
              {isExpanded && (
                <CollabDetail
                  personA={displayName}
                  personB={neighborDisplayName}
                  detail={collabDetail}
                  loading={collabLoading}
                  nameMode={personNameMode}
                />
              )}
            </li>
          )
        })}
      </ul>

      {/* Footer */}
      <div className={`mt-3 shrink-0 border-t ${dividerClass} pt-3`}>
        <a
          href={personUrl(nodeId)}
          target="_blank"
          rel="noopener noreferrer"
          className={mutedLink}
        >
          Bangumi 页面 →
        </a>
      </div>
    </div>
  )
}
