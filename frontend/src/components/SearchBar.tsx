import { useState, useCallback, useRef, useEffect } from 'react'
import type { SearchEntry } from '../types'

interface SearchBarProps {
  entries: SearchEntry[]
  onSelect: (id: string) => void
}

export function SearchBar({ entries, onSelect }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const results = query.length >= 1
    ? entries.filter(e => e.name.includes(query)).slice(0, 8)
    : []

  const handleSelect = useCallback(
    (id: string) => {
      setQuery('')
      setOpen(false)
      onSelect(id)
    },
    [onSelect],
  )

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative w-72">
      <input
        type="text"
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        placeholder="搜索人物…"
        className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-violet-500 backdrop-blur"
      />
      {open && results.length > 0 && (
        <ul className="absolute top-full mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg overflow-hidden shadow-xl z-50">
          {results.map(entry => (
            <li key={entry.id}>
              <button
                className="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 flex gap-2"
                onClick={() => handleSelect(entry.id)}
              >
                <span>{entry.name}</span>
                {entry.degree !== undefined && (
                  <span className="text-slate-500 text-xs ml-auto">{entry.degree}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
