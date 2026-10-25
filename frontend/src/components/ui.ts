// Shared UI tokens. Neutral dark surfaces, one accent (amber #f5c76b — the same
// color the galaxy uses for the selected person), hierarchy from size and weight.
// Text never goes below 12px or dimmer than zinc-500.

export const ACCENT = '#f5c76b'

export const panelShell = 'rounded-lg border border-white/[0.08] bg-[#16171b] shadow-[0_8px_32px_rgba(0,0,0,0.45)]'
export const panelSoft = 'rounded-md border border-white/[0.06] bg-white/[0.03]'
export const panelInset = 'rounded-md bg-black/25'
export const sectionLabel = 'text-xs font-medium text-zinc-400'
export const subtleLink = 'text-zinc-100 underline-offset-2 hover:text-[#f5c76b] hover:underline transition-colors'
export const mutedLink = 'text-zinc-400 hover:text-zinc-100 transition-colors'
export const faintText = 'text-zinc-500'
export const dividerClass = 'border-white/[0.08]'

export const iconButton = 'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-white/[0.06] hover:text-zinc-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#f5c76b]'

export const segmentedGroupClass = 'inline-flex shrink-0 rounded-md border border-white/[0.08] bg-black/30 p-0.5 text-xs'

export function segmentedButtonClass(active: boolean) {
  return [
    'whitespace-nowrap rounded px-2 py-1 transition-colors',
    active ? 'bg-white/[0.1] text-zinc-50' : 'text-zinc-400 hover:text-zinc-100',
  ].join(' ')
}

export function smallPillClass() {
  return 'rounded bg-white/[0.06] px-1.5 py-0.5 text-xs text-zinc-300'
}
