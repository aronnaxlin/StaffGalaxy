export interface GalaxyNode {
  id: string
  name: string
  nameCn?: string
  nameTw?: string
  degree?: number
  x?: number
  y?: number
  visibleWeightedDegree?: number
  nodeSize?: number
  roleLayer?: string
  isCenter?: boolean
  sharedWorksCount?: number
  collaborationScore?: number
  firstYear?: number
  lastYear?: number
  neighborRoleTier?: string
}

export interface GalaxyEdge {
  source: string
  target: string
  sharedWorksCount: number
  collaborationScore?: number
  firstYear?: number
  lastYear?: number
  selectionReason?: string
}

export interface SearchEntry {
  id: string
  name: string
  nameCn?: string
  nameTw?: string
  degree?: number
}

export type PersonNameMode = 'original' | 'cn' | 'tw'

export interface PersonNameLike {
  name: string
  nameCn?: string
  nameTw?: string
}

export interface SubjectNameLike {
  subjectName: string
  subjectNameCn: string
}

export interface DataSnapshot {
  snapshotId: string
  archiveName: string
  archiveCreatedAt: string
  archiveSizeBytes: number
  builtAt: string
  sourceUrl: string
}

export interface DataSource {
  label: string
  dbPath: string
  snapshot: DataSnapshot | null
}

export interface GraphManifest {
  nodes: number
  edges: number
  layoutMethod: string
  geometryFingerprint: number
}

export interface Manifest {
  version: number
  db_path: string
  snapshot: DataSnapshot | null
  graph: GraphManifest
}

export interface SharedWork {
  subjectId: number
  subjectName: string
  subjectNameCn: string
  year: number | null
  date: string | null
  personARoles: string
  personBRoles: string
}

export interface PathStep {
  source: string
  target: string
  sharedWorksCount: number
  collaborationScore: number
}

export interface PathPerson {
  id: string
  name: string
  nameCn?: string
  nameTw?: string
}

export interface SinglePath {
  nodes: string[]
  steps: PathStep[]
}

export interface PathResult {
  found: boolean
  reason?: string
  degree?: number
  pathCount?: number
  people?: PathPerson[]
  paths?: SinglePath[]
}

export interface CollaborationDetail {
  personA: { id: string; name: string; nameCn?: string; nameTw?: string }
  personB: { id: string; name: string; nameCn?: string; nameTw?: string }
  sharedWorksCount: number
  collaborationScore: number
  firstYear: number | null
  lastYear: number | null
  selectionReason: string
  sharedWorks: SharedWork[]
  source: DataSource
}

export interface PersonRoleSummary {
  position: string
  normalizedRole: string
  roleTier: string
  creditCount: number
}

export interface PersonRecentWork {
  subjectId: number
  subjectName: string
  subjectNameCn: string
  year: number | null
  date: string | null
  roles: string
  maxRoleWeight: number
}

export interface PersonCredit {
  subjectId: number
  subjectName: string
  subjectNameCn: string
  year: number | null
  date: string | null
  positionId: number | null
  position: string
  positionEn: string
  rawPosition: string
  normalizedRole: string
  roleTier: string
  roleWeight: number
  appearEps: string
}

export interface PersonCreditsResponse {
  person: {
    id: string
    name: string
    nameCn?: string
    nameTw?: string
  }
  total: number
  limit: number
  offset: number
  credits: PersonCredit[]
  source: DataSource
}

export interface PersonDetail {
  person: {
    id: string
    name: string
    nameCn?: string
    nameTw?: string
    career: unknown[]
    summary: string
  }
  stats: {
    animeCreditCount: number
    animeSubjectCount: number
    tierSCount: number
    tierACount: number
    tierBCount: number
    tierCCount: number
    tierDCount: number
    tierEFCount: number
    firstCreditYear: number | null
    latestCreditYear: number | null
  }
  topRoles: PersonRoleSummary[]
  recentWorks: PersonRecentWork[]
  source: DataSource
}

export interface KnowledgeGraphPersonNode extends PersonNameLike {
  key: string
  kind: 'person'
  id: string
  isCenter: boolean
  sharedWorksCount?: number
  collaborationScore?: number
}

export interface KnowledgeGraphAnimeNode {
  key: string
  kind: 'anime'
  id: string
  name: string
  nameCn: string
  year: number | null
}

export type KnowledgeGraphNode = KnowledgeGraphPersonNode | KnowledgeGraphAnimeNode

export interface KnowledgeGraphLink {
  source: string
  target: string
  roles: string[]
  roleTier: string
  roleWeight: number
}

export interface PersonKnowledgeGraph {
  centerId: string
  nodes: KnowledgeGraphNode[]
  links: KnowledgeGraphLink[]
}
