const bangumiBaseUrl = (import.meta.env.VITE_BANGUMI_BASE_URL ?? 'https://bgm.tv').replace(/\/+$/, '')

export function personUrl(personId: string | number) {
  return `${bangumiBaseUrl}/person/${personId}`
}

export function subjectUrl(subjectId: string | number) {
  return `${bangumiBaseUrl}/subject/${subjectId}`
}
