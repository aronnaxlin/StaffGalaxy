import type { PersonNameMode, PersonNameLike, SubjectNameLike } from '../types'

export const PERSON_NAME_MODE_KEY = 'staffGalaxy.personNameMode'

export function getInitialPersonNameMode(): PersonNameMode {
  const stored = window.localStorage.getItem(PERSON_NAME_MODE_KEY)
  if (stored === 'tw') return 'tw'
  return stored === 'cn' ? 'cn' : 'original'
}

export function displayPersonName(person: PersonNameLike, mode: PersonNameMode): string {
  if (mode === 'cn' && person.nameCn) return person.nameCn
  if (mode === 'tw') return person.nameTw || person.nameCn || person.name
  return person.name
}

export function secondaryPersonName(person: PersonNameLike, mode: PersonNameMode): string {
  const primary = displayPersonName(person, mode)
  return primary !== person.name ? person.name : ''
}

export function displaySubjectName(subject: SubjectNameLike, mode: PersonNameMode): string {
  if (mode !== 'original' && subject.subjectNameCn) return subject.subjectNameCn
  return subject.subjectName
}

export function secondarySubjectName(subject: SubjectNameLike, mode: PersonNameMode): string {
  const primary = displaySubjectName(subject, mode)
  return primary !== subject.subjectName ? subject.subjectName : ''
}
