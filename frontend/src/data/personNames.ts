import type { PersonNameMode, PersonNameLike } from '../types'

export const PERSON_NAME_MODE_KEY = 'staffGalaxy.personNameMode'

export function getInitialPersonNameMode(): PersonNameMode {
  const stored = window.localStorage.getItem(PERSON_NAME_MODE_KEY)
  if (stored === 'tw') return 'tw'
  return stored === 'cn' ? 'cn' : 'original'
}

export function displayPersonName(person: PersonNameLike, mode: PersonNameMode): string {
  if (mode === 'cn' && person.nameCn) return person.nameCn
  if (mode === 'tw' && person.nameTw) return person.nameTw
  return person.name
}

export function secondaryPersonName(person: PersonNameLike, mode: PersonNameMode): string {
  const primary = displayPersonName(person, mode)
  return primary !== person.name ? person.name : ''
}
