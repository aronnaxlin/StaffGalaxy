import { Suspense, lazy, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Collapsible, Popover, Tabs, ToggleGroup, Tooltip } from 'radix-ui'
import { ChevronDown, ExternalLink, ListFilter, Route, X } from 'lucide-react'
import {
  loadCollaborationDetail,
  loadPersonCredits,
  loadPersonDetail,
  loadPersonKnowledgeGraph,
} from '../data/loader'
import { personUrl, subjectUrl } from '../data/links'
import { displayPersonName, displaySubjectName, secondaryPersonName } from '../data/personNames'
import type {
  CollaborationDetail,
  KnowledgeGraphAnimeNode,
  KnowledgeGraphNode,
  PersonCredit,
  PersonCreditsResponse,
  PersonDetail,
  PersonKnowledgeGraph,
  PersonNameMode,
} from '../types'
import { iconButton, mutedLink, panelShell, segmentedButtonClass, segmentedGroupClass, subtleLink } from './ui'

const LocalKnowledgeGraph = lazy(() => import('./LocalKnowledgeGraph').then(module => ({
  default: module.LocalKnowledgeGraph,
})))

export interface NeighborInfo {
  id: string
  attrs: Record<string, unknown>
  sharedWorksCount: number
  collaborationScore: number
  firstYear?: number
  lastYear?: number
}

type RoleFilter = 'all' | 'sab' | 'cd' | 'ef'
type TimeFilter = 'all' | 'recent10' | 'since2010' | 'since2000'

const LIMIT_OPTIONS = ['60', '120', '240'] as const
const MIN_SHARED_OPTIONS = ['1', '3', '5', '10'] as const
const ROLE_OPTIONS: { value: RoleFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'sab', label: '主创 S/A/B' },
  { value: 'cd', label: 'C/D' },
  { value: 'ef', label: 'E/F' },
]
const TIME_OPTIONS: { value: TimeFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'recent10', label: '近 10 年' },
  { value: 'since2010', label: '2010 后' },
  { value: 'since2000', label: '2000 后' },
]

function yearRange(first: number | null | undefined, last: number | null | undefined) {
  if (!first && !last) return null
  if (first && last && first !== last) return `${first}–${last}`
  return String(first ?? last)
}

function matchesRole(tier: unknown, filter: RoleFilter) {
  if (filter === 'all') return true
  const t = String(tier ?? '').match(/[SABCDEF]/)?.[0]
  if (!t) return false
  if (filter === 'sab') return 'SAB'.includes(t)
  if (filter === 'cd') return 'CD'.includes(t)
  return 'EF'.includes(t)
}

function matchesTime(lastYear: number | undefined, filter: TimeFilter) {
  if (filter === 'all') return true
  if (!lastYear) return false
  if (filter === 'recent10') return lastYear >= new Date().getFullYear() - 10
  return lastYear >= (filter === 'since2010' ? 2010 : 2000)
}

function Hint({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content sideOffset={4} className="z-[60] rounded bg-zinc-800 px-2 py-1 text-xs text-zinc-100 shadow-lg">
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={next => { if (next) onChange(next as T) }}
      className={segmentedGroupClass}
    >
      {options.map(option => (
        <ToggleGroup.Item key={option.value} value={option.value} className={segmentedButtonClass(value === option.value)}>
          {option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  )
}

function CollabWorks({ detail, nameA, nameB, nameMode }: {
  detail: CollaborationDetail | null
  nameA: string
  nameB: string
  nameMode: PersonNameMode
}) {
  if (!detail) return <div className="px-2 pb-2 text-xs text-zinc-500">加载中…</div>
  return (
    <ul className="mx-2 mb-2 space-y-2 border-l border-white/[0.08] pl-3">
      {detail.sharedWorks.map(work => (
        <li key={work.subjectId} className="text-xs leading-relaxed">
          <div className="flex items-baseline justify-between gap-2">
            <a href={subjectUrl(work.subjectId)} target="_blank" rel="noopener noreferrer" className={`${subtleLink} truncate text-sm`}>
              {displaySubjectName(work, nameMode)}
            </a>
            <span className="shrink-0 tabular-nums text-zinc-500">{work.year ?? ''}</span>
          </div>
          <div className="text-zinc-400"><span className="text-zinc-500">{nameA}：</span>{work.personARoles || '—'}</div>
          <div className="text-zinc-400"><span className="text-zinc-500">{nameB}：</span>{work.personBRoles || '—'}</div>
        </li>
      ))}
    </ul>
  )
}

function CollaboratorsTab({
  personId,
  displayName,
  neighbors,
  limit,
  minShared,
  onLimitChange,
  onMinSharedChange,
  nameMode,
  onSelect,
  onCompare,
}: {
  personId: string
  displayName: string
  neighbors: NeighborInfo[]
  limit: number
  minShared: number
  onLimitChange: (value: number) => void
  onMinSharedChange: (value: number) => void
  nameMode: PersonNameMode
  onSelect: (id: string) => void
  onCompare: (a: string, b: string) => void
}) {
  const [role, setRole] = useState<RoleFilter>('all')
  const [time, setTime] = useState<TimeFilter>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<CollaborationDetail | null>(null)

  useEffect(() => {
    setExpandedId(null)
  }, [personId])

  useEffect(() => {
    if (!expandedId) return
    let cancelled = false
    setDetail(null)
    loadCollaborationDetail(personId, expandedId)
      .then(data => { if (!cancelled) setDetail(data) })
      .catch(() => { if (!cancelled) setDetail(null) })
    return () => { cancelled = true }
  }, [expandedId, personId])

  const visible = useMemo(
    () => neighbors.filter(n => matchesRole(n.attrs.neighborRoleTier, role) && matchesTime(n.lastYear, time)),
    [neighbors, role, time],
  )
  const activeFilters = Number(role !== 'all') + Number(time !== 'all') + Number(minShared > 1)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-4 py-2 text-xs text-zinc-400">
        <span>{visible.length === neighbors.length ? `${neighbors.length} 位骨干合作者` : `${visible.length} / ${neighbors.length} 位`}</span>
        <Popover.Root>
          <Popover.Trigger className={`${mutedLink} inline-flex items-center gap-1 rounded px-1.5 py-1 hover:bg-white/[0.06]`}>
            <ListFilter size={14} />
            筛选{activeFilters > 0 ? ` · ${activeFilters}` : ''}
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content align="end" sideOffset={6} className={`${panelShell} z-[60] w-80 space-y-3 p-3 text-xs text-zinc-400`}>
              <div className="space-y-1.5">
                <div>至少合作几部</div>
                <Segmented
                  value={String(minShared) as (typeof MIN_SHARED_OPTIONS)[number]}
                  options={MIN_SHARED_OPTIONS.map(v => ({ value: v, label: `${v} 部+` }))}
                  onChange={v => onMinSharedChange(Number(v))}
                />
              </div>
              <div className="space-y-1.5">
                <div>对方在共同作品中的最高职位</div>
                <Segmented value={role} options={ROLE_OPTIONS} onChange={setRole} />
              </div>
              <div className="space-y-1.5">
                <div>最后一次合作</div>
                <Segmented value={time} options={TIME_OPTIONS} onChange={setTime} />
              </div>
              <div className="space-y-1.5">
                <div>最多加载</div>
                <Segmented
                  value={String(limit) as (typeof LIMIT_OPTIONS)[number]}
                  options={LIMIT_OPTIONS.map(v => ({ value: v, label: `${v} 人` }))}
                  onChange={v => onLimitChange(Number(v))}
                />
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>

      <div className="grid grid-cols-[1fr_auto_2.5rem_3.5rem] gap-2 border-y border-white/[0.06] px-4 py-1.5 text-xs text-zinc-500">
        <span>合作者</span>
        <span>年份</span>
        <span className="text-right">作品</span>
        <span />
      </div>

      <ul className="min-h-0 flex-1 overflow-y-auto px-2 py-1">
        {visible.length === 0 && (
          <li className="px-2 py-3 text-sm text-zinc-500">
            {neighbors.length === 0 ? '这个人不在星系骨干里，可以在「知识图谱」里看他的合作关系。' : '当前筛选下没有合作者。'}
          </li>
        )}
        {visible.map(n => {
          const person = { name: n.attrs.name as string, nameCn: n.attrs.nameCn as string | undefined, nameTw: n.attrs.nameTw as string | undefined }
          const name = displayPersonName(person, nameMode)
          const secondary = secondaryPersonName(person, nameMode)
          const open = expandedId === n.id
          return (
            <Collapsible.Root asChild key={n.id} open={open} onOpenChange={value => setExpandedId(value ? n.id : null)}>
              <li className={`rounded-md ${open ? 'bg-white/[0.04]' : ''}`}>
                <div className="grid grid-cols-[1fr_auto_2.5rem_3.5rem] items-center gap-2 rounded-md px-2 py-1.5 hover:bg-white/[0.04]">
                  <button type="button" onClick={() => onSelect(n.id)} className="min-w-0 text-left">
                    <div className="truncate text-sm text-zinc-100 hover:text-[#f5c76b]">{name}</div>
                    {secondary && <div className="truncate text-xs text-zinc-500">{secondary}</div>}
                  </button>
                  <span className="text-xs tabular-nums text-zinc-500">{yearRange(n.firstYear, n.lastYear) ?? ''}</span>
                  <span className="text-right text-sm tabular-nums text-zinc-200">{n.sharedWorksCount}</span>
                  <span className="flex justify-end">
                    <Hint label="合作作品">
                      <Collapsible.Trigger className={iconButton}>
                        <ChevronDown size={15} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
                      </Collapsible.Trigger>
                    </Hint>
                    <Hint label="在关系星图中比较">
                      <button type="button" className={iconButton} onClick={() => onCompare(personId, n.id)}>
                        <Route size={15} />
                      </button>
                    </Hint>
                  </span>
                </div>
                <Collapsible.Content>
                  <CollabWorks detail={detail} nameA={displayName} nameB={name} nameMode={nameMode} />
                </Collapsible.Content>
              </li>
            </Collapsible.Root>
          )
        })}
      </ul>
    </div>
  )
}

function groupCredits(credits: PersonCredit[]) {
  const bySubject = new Map<number, { work: PersonCredit; roles: string[] }>()
  for (const credit of credits) {
    const group = bySubject.get(credit.subjectId)
    const role = credit.rawPosition || credit.position
    if (group) {
      if (!group.roles.includes(role)) group.roles.push(role)
    } else {
      bySubject.set(credit.subjectId, { work: credit, roles: [role] })
    }
  }
  return Array.from(bySubject.values())
}

function CreditsTab({ personId, nameMode }: { personId: string; nameMode: PersonNameMode }) {
  const [credits, setCredits] = useState<PersonCreditsResponse | null>(null)
  useEffect(() => {
    let cancelled = false
    setCredits(null)
    loadPersonCredits(personId).then(data => { if (!cancelled) setCredits(data) }).catch(() => {})
    return () => { cancelled = true }
  }, [personId])
  const groups = useMemo(() => groupCredits(credits?.credits ?? []), [credits])

  if (!credits) return <div className="px-4 py-3 text-sm text-zinc-500">加载中…</div>
  return (
    <ul className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-4 py-3">
      {groups.map(({ work, roles }) => (
        <li key={work.subjectId} className="text-sm leading-snug">
          <div className="flex items-baseline justify-between gap-2">
            <a href={subjectUrl(work.subjectId)} target="_blank" rel="noopener noreferrer" className={`${subtleLink} truncate`}>
              {displaySubjectName(work, nameMode)}
            </a>
            <span className="shrink-0 text-xs tabular-nums text-zinc-500">{work.year ?? ''}</span>
          </div>
          <div className="text-xs text-zinc-400">{roles.join('、')}</div>
        </li>
      ))}
      {credits.total > credits.credits.length && (
        <li className="text-xs text-zinc-500">只显示前 {credits.credits.length} / {credits.total} 条记录。</li>
      )}
    </ul>
  )
}

function nodeName(node: KnowledgeGraphNode, mode: PersonNameMode) {
  if (node.kind === 'person') return displayPersonName(node, mode)
  return mode !== 'original' && node.nameCn ? node.nameCn : node.name
}

function KnowledgeGraphTab({ personId, nameMode, onSelect }: {
  personId: string
  nameMode: PersonNameMode
  onSelect: (id: string) => void
}) {
  const [graph, setGraph] = useState<PersonKnowledgeGraph | null>(null)
  const [failed, setFailed] = useState(false)
  const [hoverKey, setHoverKey] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    setFailed(false)
    setHoverKey(null)
    loadPersonKnowledgeGraph(personId)
      .then(data => { if (!cancelled) setGraph(data) })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [personId])

  // The triples behind the drawing: every CREDITED relationship touching the
  // hovered node (or the center), read as (person) —[roles]→ (anime).
  const focusKey = hoverKey ?? (graph ? `p:${graph.centerId}` : null)
  const triples = useMemo(() => {
    if (!graph || !focusKey) return []
    const byKey = new Map(graph.nodes.map(node => [node.key, node]))
    return graph.links
      .filter(link => link.source === focusKey || link.target === focusKey)
      .sort((a, b) => b.roleWeight - a.roleWeight)
      .map(link => ({
        key: `${link.source}|${link.target}`,
        subject: nodeName(byKey.get(link.source)!, nameMode),
        roles: link.roles.length > 4 ? `${link.roles.slice(0, 4).join('、')} 等 ${link.roles.length} 项` : link.roles.join('、'),
        object: nodeName(byKey.get(link.target)!, nameMode),
        year: (byKey.get(link.target) as KnowledgeGraphAnimeNode | undefined)?.year ?? null,
      }))
  }, [focusKey, graph, nameMode])
  const focusName = graph && focusKey ? nodeName(graph.nodes.find(node => node.key === focusKey)!, nameMode) : ''

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative h-[min(24rem,45vh)] shrink-0 bg-black/20">
        {failed && <div className="px-4 py-3 text-sm text-zinc-500">知识图谱加载失败。</div>}
        {!failed && !graph && <div className="px-4 py-3 text-sm text-zinc-500">加载中…</div>}
        {!failed && graph && (
          <Suspense fallback={null}>
            <LocalKnowledgeGraph graph={graph} personNameMode={nameMode} onSelectPerson={onSelect} onHoverChange={setHoverKey} />
          </Suspense>
        )}
        <div className="pointer-events-none absolute bottom-2 left-3 flex gap-3 text-xs text-zinc-400">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#f5c76b]" />当前</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-zinc-300" />人物</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-[#8ab4c9]" />作品</span>
        </div>
      </div>
      <div className="flex items-baseline justify-between border-y border-white/[0.06] px-4 py-2">
        <span className="text-xs font-medium text-zinc-300">三元组 · {focusName}</span>
        <span className="text-xs text-zinc-500">悬停节点切换 · 点人物换中心</span>
      </div>
      <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto px-4 py-2 text-sm">
        {triples.map(triple => (
          <li key={triple.key} className="leading-snug text-zinc-300">
            <span className="text-zinc-100">{triple.subject}</span>
            <span className="text-zinc-500"> —[</span>
            <span className="text-zinc-400">{triple.roles}</span>
            <span className="text-zinc-500">]→ </span>
            <span className="text-zinc-100">{triple.object}</span>
            {triple.year && <span className="ml-1 text-xs text-zinc-500">{triple.year}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PersonSidebar({
  personId,
  galaxyAttrs,
  neighbors,
  neighborLimit,
  neighborMinShared,
  onNeighborLimitChange,
  onNeighborMinSharedChange,
  nameMode,
  onClose,
  onSelectPerson,
  onCompare,
}: {
  personId: string
  galaxyAttrs: Record<string, unknown>
  neighbors: NeighborInfo[]
  neighborLimit: number
  neighborMinShared: number
  onNeighborLimitChange: (value: number) => void
  onNeighborMinSharedChange: (value: number) => void
  nameMode: PersonNameMode
  onClose: () => void
  onSelectPerson: (id: string) => void
  onCompare: (a: string, b: string) => void
}) {
  const [detail, setDetail] = useState<PersonDetail | null>(null)
  const [tab, setTab] = useState('graph')

  useEffect(() => {
    let cancelled = false
    setDetail(null)
    loadPersonDetail(personId).then(data => { if (!cancelled) setDetail(data) }).catch(() => {})
    return () => { cancelled = true }
  }, [personId])

  // People outside the galaxy have no galaxy attrs; the detail endpoint still has names.
  const person = {
    name: (galaxyAttrs.name as string | undefined) ?? detail?.person.name ?? `#${personId}`,
    nameCn: (galaxyAttrs.nameCn as string | undefined) ?? detail?.person.nameCn,
    nameTw: (galaxyAttrs.nameTw as string | undefined) ?? detail?.person.nameTw,
  }
  const displayName = displayPersonName(person, nameMode)
  const secondary = secondaryPersonName(person, nameMode)
  const stats = detail?.stats
  const range = stats ? yearRange(stats.firstCreditYear, stats.latestCreditYear) : null
  const summary = stats
    ? [`参与 ${stats.animeSubjectCount} 部动画`, range, `${stats.animeCreditCount} 条职位记录`].filter(Boolean).join(' · ')
    : '加载中…'
  const topRoles = detail?.topRoles.slice(0, 4).map(role => `${role.position} ${role.creditCount}`).join(' · ')
  const snapshotDate = detail?.source.snapshot?.archiveCreatedAt?.slice(0, 10)

  const tabClass = 'relative px-1 pb-2 text-sm text-zinc-400 transition-colors hover:text-zinc-100 data-[state=active]:text-zinc-50 data-[state=active]:after:absolute data-[state=active]:after:inset-x-0 data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5 data-[state=active]:after:bg-[#f5c76b]'

  return (
    <aside className="relative z-40 flex h-full w-[min(27rem,100vw)] shrink-0 flex-col overflow-hidden border-l border-white/[0.08] bg-[#16171b]">
      <header className="px-4 pb-3 pt-4">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold text-zinc-50">{displayName}</h2>
            {secondary && <div className="truncate text-sm text-zinc-400">{secondary}</div>}
          </div>
          <Hint label="Bangumi 人物页">
            <a href={personUrl(personId)} target="_blank" rel="noopener noreferrer" className={iconButton}>
              <ExternalLink size={15} />
            </a>
          </Hint>
          <Hint label="关闭">
            <button type="button" onClick={onClose} className={iconButton}><X size={16} /></button>
          </Hint>
        </div>
        <div className="mt-2 text-sm text-zinc-300">{summary}</div>
        {topRoles && <div className="mt-1 truncate text-xs text-zinc-500">常见职位：{topRoles}</div>}
      </header>

      <Tabs.Root value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
        <Tabs.List className="flex gap-5 border-b border-white/[0.08] px-4">
          <Tabs.Trigger value="graph" className={tabClass}>知识图谱</Tabs.Trigger>
          <Tabs.Trigger value="collaborators" className={tabClass}>合作者</Tabs.Trigger>
          <Tabs.Trigger value="credits" className={tabClass}>履历</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="collaborators" className="flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden">
          <CollaboratorsTab
            personId={personId}
            displayName={displayName}
            neighbors={neighbors}
            limit={neighborLimit}
            minShared={neighborMinShared}
            onLimitChange={onNeighborLimitChange}
            onMinSharedChange={onNeighborMinSharedChange}
            nameMode={nameMode}
            onSelect={onSelectPerson}
            onCompare={onCompare}
          />
        </Tabs.Content>
        <Tabs.Content value="graph" className="flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden">
          {tab === 'graph' && <KnowledgeGraphTab personId={personId} nameMode={nameMode} onSelect={onSelectPerson} />}
        </Tabs.Content>
        <Tabs.Content value="credits" className="flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden">
          {tab === 'credits' && <CreditsTab personId={personId} nameMode={nameMode} />}
        </Tabs.Content>
      </Tabs.Root>

      <footer className="border-t border-white/[0.06] px-4 py-2 text-xs text-zinc-500">
        数据：Bangumi Archive{snapshotDate ? ` ${snapshotDate}` : ''} · 社区维护，可能不完整
      </footer>
    </aside>
  )
}
