import { useState, useCallback, useEffect, useMemo } from 'react'
import { loadCollaborationDetail, loadPersonCredits, loadPersonDetail } from '../data/loader'
import { personUrl, subjectUrl } from '../data/links'
import { displayPersonName, secondaryPersonName } from '../data/personNames'
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
  personNameMode: PersonNameMode
  onPersonNameModeChange: (mode: PersonNameMode) => void
  onClose: () => void
  onNodeClick: (id: string) => void
  onCompare: (personAId: string, personBId: string) => void
}

type SubjectNameMode = 'original' | 'cn'

const SUBJECT_NAME_MODE_KEY = 'staffGalaxy.subjectNameMode'

function getInitialSubjectNameMode(): SubjectNameMode {
  const stored = window.localStorage.getItem(SUBJECT_NAME_MODE_KEY)
  return stored === 'cn' ? 'cn' : 'original'
}

function subjectDisplayName(
  work: { subjectName: string; subjectNameCn: string },
  mode: SubjectNameMode,
) {
  if (mode === 'cn' && work.subjectNameCn) {
    return { primary: work.subjectNameCn, secondary: work.subjectName }
  }
  return { primary: work.subjectName, secondary: work.subjectNameCn }
}

function yearRange(first: number | null, latest: number | null) {
  if (!first && !latest) return null
  if (first && latest && first !== latest) return `${first}–${latest}`
  return String(first ?? latest)
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
  subjectNameMode,
}: {
  detail: PersonDetail | null
  loading: boolean
  subjectNameMode: SubjectNameMode
}) {
  if (loading) {
    return (
      <div className={`${panelSoft} mb-3 px-3 py-2 text-xs text-slate-500`}>
        履历加载中…
      </div>
    )
  }

  if (!detail) return null

  const range = yearRange(detail.stats.firstCreditYear, detail.stats.latestCreditYear)

  return (
    <div className={`${panelSoft} mb-3 shrink-0 p-3`}>
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
            {detail.recentWorks.slice(0, 4).map(work => {
              const display = subjectDisplayName(work, subjectNameMode)
              return (
                <li key={work.subjectId} className="text-[11px] leading-snug">
                  <a
                    href={subjectUrl(work.subjectId)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={subtleLink}
                    title={`Bangumi subject #${work.subjectId}`}
                  >
                    {display.primary}
                  </a>
                  {work.year && <span className="ml-1 text-slate-600">{work.year}</span>}
                  {work.roles && <div className="truncate text-slate-600">{work.roles}</div>}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <div className={`mt-2 truncate border-t ${dividerClass} pt-2 text-[10px] text-slate-700`}>
        {detail.source.label} · {snapshotLabel(detail)}
      </div>
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
  subjectNameMode,
  onToggle,
}: {
  credits: PersonCreditsResponse | null
  loading: boolean
  open: boolean
  total: number | null
  subjectNameMode: SubjectNameMode
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
                  const display = subjectDisplayName(group, subjectNameMode)
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
                          {display.primary}
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
  subjectNameMode,
  onSubjectNameModeChange,
}: {
  personA: string
  personB: string
  detail: CollaborationDetail | null
  loading: boolean
  subjectNameMode: SubjectNameMode
  onSubjectNameModeChange: (mode: SubjectNameMode) => void
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
        <div className={`${segmentedGroupClass} ml-auto`}>
          {(['original', 'cn'] as const).map(mode => (
            <button
              key={mode}
              type="button"
              onClick={() => onSubjectNameModeChange(mode)}
              className={segmentedButtonClass(subjectNameMode === mode, 'cyan')}
            >
              {mode === 'original' ? '原名' : '中文'}
            </button>
          ))}
        </div>
      </div>
      <div className="mb-2 truncate text-[10px] text-slate-700">
        数据快照：{snapshotLabel(detail)}
      </div>
      <ul className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
        {detail.sharedWorks.map(work => {
          const display = subjectDisplayName(work, subjectNameMode)
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
                  {display.primary}
                </a>
                {display.secondary && display.secondary !== display.primary && (
                  <span className="text-slate-500 ml-1">({display.secondary})</span>
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
  personNameMode,
  onPersonNameModeChange,
  onClose,
  onNodeClick,
  onCompare,
}: NodePanelProps) {
  const name = nodeAttrs.name as string
  const nameCn = nodeAttrs.nameCn as string | undefined
  const displayName = displayPersonName({ name, nameCn }, personNameMode)
  const secondaryName = secondaryPersonName({ name, nameCn }, personNameMode)
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
  const [subjectNameMode, setSubjectNameMode] = useState<SubjectNameMode>(getInitialSubjectNameMode)

  useEffect(() => {
    window.localStorage.setItem(SUBJECT_NAME_MODE_KEY, subjectNameMode)
  }, [subjectNameMode])

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
    <div className={`${panelShell} absolute right-4 top-16 z-40 flex max-h-[calc(100dvh-6rem)] w-96 flex-col overflow-hidden p-4`}>
      {/* Header */}
      <div className="mb-3 flex shrink-0 items-start justify-between">
        <div className="min-w-0">
          <div className="text-base font-semibold text-slate-100 truncate">{displayName}</div>
          {secondaryName && (
            <div className="mt-0.5 truncate text-[11px] text-slate-600">{secondaryName}</div>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-slate-400">
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
          <div className={`${segmentedGroupClass} mt-2 w-fit`}>
            {(['original', 'cn'] as const).map(mode => (
              <button
                key={mode}
                type="button"
                onClick={() => onPersonNameModeChange(mode)}
                className={segmentedButtonClass(personNameMode === mode, 'cyan')}
              >
                {mode === 'original' ? '原名' : '简中'}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={onClose}
          className="ml-2 shrink-0 text-lg leading-none text-slate-500 transition-colors hover:text-pink-300"
        >
          ×
        </button>
      </div>

      <PersonSummary
        detail={personDetail}
        loading={personDetailLoading}
        subjectNameMode={subjectNameMode}
      />

      <PersonCreditsHistory
        credits={personCredits}
        loading={personCreditsLoading}
        open={personCreditsOpen}
        total={personDetail?.stats.animeCreditCount ?? personCredits?.total ?? null}
        subjectNameMode={subjectNameMode}
        onToggle={() => void handleToggleCredits()}
      />

      {/* Neighbor list header */}
      <div className="mb-2 flex shrink-0 items-center justify-between text-xs text-slate-500">
        <span className={sectionLabel}>按合作次数排序</span>
        {neighborTotal > neighbors.length && (
          <span>前 {neighbors.length} / {neighborTotal}</span>
        )}
      </div>

      {/* Neighbor list */}
      <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1">
        {neighbors.map(({ id, attrs, sharedWorksCount, collaborationScore, firstYear, lastYear }) => {
          const isExpanded = expandedId === id
          const neighborName = attrs.name as string
          const neighborNameCn = attrs.nameCn as string | undefined
          const neighborDisplayName = displayPersonName(
            { name: neighborName, nameCn: neighborNameCn },
            personNameMode,
          )
          const neighborSecondaryName = secondaryPersonName(
            { name: neighborName, nameCn: neighborNameCn },
            personNameMode,
          )
          return (
            <li key={id}>
              <button
                className="group w-full rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-slate-900/70"
                onClick={() => onNodeClick(id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-slate-300 transition-colors group-hover:text-cyan-300">
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
                      <span className="min-w-[1.5rem] rounded-full border border-slate-700/40 bg-slate-950/50 px-1.5 py-0.5 text-right text-[10px] tabular-nums text-slate-400">
                        {sharedWorksCount}
                      </span>
                  </div>
                </div>
                {collaborationScore > 0 && (
                  <div className="flex items-center gap-1 mt-0.5">
                    <div
                      className="h-0.5 rounded-full bg-cyan-500/70"
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
                    ? 'bg-cyan-950/30 text-cyan-300'
                    : 'text-slate-600 hover:text-slate-400'
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
                className="w-full rounded px-2 py-0.5 text-left text-[11px] text-slate-600 transition-colors hover:bg-pink-950/20 hover:text-pink-300"
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
                  subjectNameMode={subjectNameMode}
                  onSubjectNameModeChange={setSubjectNameMode}
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
