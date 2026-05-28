export interface StaffGalaxyMetric {
  name: string
  atMs: number
  route: string
  data: Record<string, string | number | boolean | null>
}

declare global {
  interface Window {
    __staffGalaxyMetrics?: StaffGalaxyMetric[]
  }
}

export function recordRuntimeMetric(
  name: string,
  data: Record<string, string | number | boolean | null> = {},
) {
  if (typeof window === 'undefined') return

  const entry: StaffGalaxyMetric = {
    name,
    atMs: Math.round(performance.now() * 10) / 10,
    route: `${window.location.pathname}${window.location.search}`,
    data,
  }

  window.__staffGalaxyMetrics = [...(window.__staffGalaxyMetrics ?? []), entry]
  window.dispatchEvent(new CustomEvent('staff-galaxy:metric', { detail: entry }))
}
