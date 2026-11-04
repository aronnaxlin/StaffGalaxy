import { Tooltip } from 'radix-ui'
import { getIncludeNsfw, setIncludeNsfw } from '../data/nsfw'
import { panelShell, segmentedButtonClass, segmentedGroupClass } from './ui'

export function NsfwToggle() {
  const include = getIncludeNsfw()
  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <div className={segmentedGroupClass}>
            <button
              type="button"
              aria-pressed={include}
              onClick={() => setIncludeNsfw(!include)}
              className={segmentedButtonClass(include)}
            >
              NSFW
            </button>
          </div>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content sideOffset={8} className={`${panelShell} z-[60] px-2.5 py-1.5 text-xs text-zinc-300`}>
            {include ? '已显示 NSFW 作品，点击隐藏' : 'NSFW 作品已隐藏，点击显示'}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
