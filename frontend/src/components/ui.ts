const ACTIVE_TONES = {
  cyan: 'border-[#6baae8]/45 bg-[#0f3e75]/70 text-[#d9ecff]',
  pink: 'border-[#f09199]/50 bg-[#9b2838]/45 text-[#ffecef]',
  slate: 'border-[#eae2cf]/20 bg-[#3d3d3f]/85 text-slate-100',
} as const

export const panelShell = 'rounded-xl border border-[#f09199]/30 bg-[rgba(38,39,40,0.92)] shadow-[0_18px_52px_rgba(0,0,0,0.42),0_0_0_1px_rgba(255,255,255,0.04)] backdrop-blur'
export const panelSoft = 'rounded-lg border border-[#d98d88]/30 bg-[rgba(61,61,63,0.68)]'
export const panelInset = 'rounded-md border border-[#eae2cf]/15 bg-[rgba(22,23,24,0.42)]'
export const sectionLabel = 'text-[10px] uppercase tracking-[0.24em] text-[#d98d88]'
export const subtleLink = 'text-[#d9ecff] hover:text-[#7ecbff] transition-colors'
export const mutedLink = 'text-slate-400 hover:text-[#7ecbff] transition-colors'
export const faintText = 'text-slate-500'
export const dividerClass = 'border-[#f09199]/20'

export const segmentedGroupClass = 'inline-flex shrink-0 overflow-hidden rounded-full border border-[#f09199]/25 bg-black/30 text-[10px] backdrop-blur'

export function segmentedButtonClass(active: boolean, tone: keyof typeof ACTIVE_TONES = 'cyan') {
  return [
    'whitespace-nowrap px-2 py-1 transition-colors',
    active ? ACTIVE_TONES[tone] : 'text-slate-400 hover:bg-[#f09199]/10 hover:text-slate-100',
  ].join(' ')
}

export function smallPillClass(active = false) {
  return active
    ? 'rounded-full border border-[#6baae8]/45 bg-[#0f3e75]/70 px-2 py-0.5 text-[10px] text-[#d9ecff]'
    : 'rounded-full border border-[#f09199]/25 bg-black/25 px-2 py-0.5 text-[10px] text-slate-300'
}
