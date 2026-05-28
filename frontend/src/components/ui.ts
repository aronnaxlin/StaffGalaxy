const ACTIVE_TONES = {
  cyan: 'border-cyan-500/30 bg-cyan-950/45 text-cyan-100',
  pink: 'border-pink-500/30 bg-pink-950/45 text-pink-100',
  slate: 'border-slate-500/30 bg-slate-800/70 text-slate-100',
} as const

export const panelShell = 'rounded-xl border border-slate-700/60 bg-[rgba(2,6,23,0.92)] shadow-[0_18px_50px_rgba(0,0,0,0.38)] backdrop-blur'
export const panelSoft = 'rounded-lg border border-slate-800/70 bg-[rgba(15,23,42,0.72)]'
export const panelInset = 'rounded-md border border-slate-800/70 bg-[rgba(15,23,42,0.45)]'
export const sectionLabel = 'text-[10px] uppercase tracking-[0.28em] text-slate-500'
export const subtleLink = 'text-slate-300 hover:text-cyan-300 transition-colors'
export const mutedLink = 'text-slate-500 hover:text-cyan-300 transition-colors'
export const faintText = 'text-slate-500'
export const dividerClass = 'border-slate-800/70'

export const segmentedGroupClass = 'inline-flex shrink-0 overflow-hidden rounded-full border border-slate-700/50 bg-black/30 text-[10px] backdrop-blur'

export function segmentedButtonClass(active: boolean, tone: keyof typeof ACTIVE_TONES = 'cyan') {
  return [
    'whitespace-nowrap px-2 py-1 transition-colors',
    active ? ACTIVE_TONES[tone] : 'text-slate-500 hover:bg-slate-900/70 hover:text-slate-300',
  ].join(' ')
}

export function smallPillClass(active = false) {
  return active
    ? 'rounded-full border border-cyan-500/30 bg-cyan-950/45 px-2 py-0.5 text-[10px] text-cyan-100'
    : 'rounded-full border border-slate-700/50 bg-slate-900/60 px-2 py-0.5 text-[10px] text-slate-400'
}
