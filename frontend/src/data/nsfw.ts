// NSFW anime are hidden from every evidence list unless the viewer opts in.
// The choice is a per-browser preference; storage can be unavailable, and then
// the safe default (hidden) applies.
const INCLUDE_NSFW_KEY = 'staffGalaxy.includeNsfw'

export function getIncludeNsfw(): boolean {
  try {
    return window.localStorage.getItem(INCLUDE_NSFW_KEY) === '1'
  } catch {
    return false
  }
}

export function setIncludeNsfw(include: boolean) {
  try {
    window.localStorage.setItem(INCLUDE_NSFW_KEY, include ? '1' : '0')
  } catch {
    // Not persisted; the reload below then falls back to hidden.
  }
  // Every panel caches its responses; a reload refetches them under the new
  // setting while the URL keeps the current view.
  window.location.reload()
}

export function withNsfw(url: string): string {
  if (!getIncludeNsfw()) return url
  return `${url}${url.includes('?') ? '&' : '?'}nsfw=true`
}
