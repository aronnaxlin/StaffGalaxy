import type { PersonNameMode } from '../types'
import { segmentedButtonClass, segmentedGroupClass } from './ui'

export function NameModeToggle({
  mode,
  onChange,
}: {
  mode: PersonNameMode
  onChange: (mode: PersonNameMode) => void
}) {
  return (
    <div className={segmentedGroupClass}>
      {(['original', 'cn', 'tw'] as const).map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={segmentedButtonClass(mode === option)}
        >
          {option === 'original' ? '原名' : option === 'cn' ? '简中' : '繁中'}
        </button>
      ))}
    </div>
  )
}
