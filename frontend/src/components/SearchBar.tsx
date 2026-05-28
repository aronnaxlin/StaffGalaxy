import { useState, useCallback, useRef, useEffect } from 'react'
import { searchPersons } from '../data/loader'
import { personUrl } from '../data/links'
import { displayPersonName, secondaryPersonName } from '../data/personNames'
import type { PersonNameMode, SearchEntry } from '../types'
import { mutedLink, panelShell, sectionLabel, subtleLink } from './ui'

interface SearchBarProps {
  onSelect: (entry: SearchEntry) => void
  selectedEntry?: SearchEntry | null
  onClear?: () => void
  personNameMode?: PersonNameMode
  className?: string
}

export function SearchBar({
  onSelect,
  selectedEntry,
  onClear,
  personNameMode = 'original',
  className = 'w-72',
}: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchEntry[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const ref = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<number | null>(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Debounced search
  useEffect(() => {
    if (query.length < 1) {
      setResults([])
      setOpen(false)
      return
    }
    if (debounceRef.current !== null) clearTimeout(debounceRef.current)

    debounceRef.current = window.setTimeout(() => {
      setLoading(true)
      searchPersons(query)
        .then((data) => {
          setResults(data)
          setOpen(data.length > 0)
          setSelectedIdx(-1)
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
    }, 180)
  }, [query])

  const commit = useCallback(
    (entry: SearchEntry) => {
      setQuery('')
      setOpen(false)
      setResults([])
      onSelect(entry)
    },
    [onSelect],
  )

  const handleClear = useCallback(() => {
    onClear?.()
    // Focus the input after clearing
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [onClear])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Backspace on empty input with a locked selection → clear
      if (e.key === 'Backspace' && query === '' && selectedEntry && onClear) {
        e.preventDefault()
        handleClear()
        return
      }
      if (!open || results.length === 0) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx(prev => (prev + 1) % results.length)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx(prev => (prev <= 0 ? results.length - 1 : prev - 1))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const idx = selectedIdx >= 0 ? selectedIdx : 0
        if (results[idx]) commit(results[idx])
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    },
    [open, results, selectedIdx, commit, selectedEntry, onClear, query, handleClear],
  )

  // Locked mode: show selected person as a pill
  if (selectedEntry) {
    const selectedName = displayPersonName(selectedEntry, personNameMode)
    const selectedSecondary = secondaryPersonName(selectedEntry, personNameMode)
    return (
      <div className={className}>
        <div
          className={`${panelShell} flex cursor-text items-center gap-2 px-3 py-2`}
          onClick={() => inputRef.current?.focus()}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm text-slate-200">{selectedName}</span>
            {selectedSecondary && (
              <span className="block truncate text-[10px] text-slate-600">{selectedSecondary}</span>
            )}
          </span>
          <span className="rounded-full border border-slate-700/50 bg-slate-900/70 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-500">
            #{selectedEntry.id}
          </span>
          <a
            href={personUrl(selectedEntry.id)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className={mutedLink}
            title="打开 Bangumi 人物页"
          >
            ↗
          </a>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleClear() }}
            className="px-0.5 text-sm leading-none text-slate-500 transition-colors hover:text-pink-300"
          >
            ×
          </button>
        </div>
        {/* Hidden input to capture keyboard events (Backspace to clear) */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (results.length > 0) setOpen(true) }}
          placeholder=""
          className="absolute opacity-0 w-0 h-0"
          autoComplete="off"
        />
      </div>
    )
  }

  // Normal mode: search input
  return (
    <div ref={ref} className={`relative ${className}`}>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
        onKeyDown={handleKeyDown}
        placeholder="搜索人名或Bangumi ID…"
        className={`${panelShell} w-full px-3 py-2 text-sm text-slate-200 outline-none transition-colors placeholder:text-slate-500 focus:border-cyan-500/50`}
        autoComplete="off"
      />
      {loading && query.length >= 1 && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="w-3.5 h-3.5 border border-slate-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {open && results.length > 0 && (
        <ul className={`${panelShell} absolute top-full z-50 mt-1 max-h-80 w-full overflow-y-auto py-1`}>
          <li className={`${sectionLabel} px-3 py-1`}>Search results</li>
          {results.map((entry, idx) => {
            const name = displayPersonName(entry, personNameMode)
            const secondary = secondaryPersonName(entry, personNameMode)
            return (
            <li key={entry.id} className="flex items-stretch">
              <button
                className={`flex min-w-0 flex-1 items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors ${
                  idx === selectedIdx
                    ? 'bg-cyan-950/35 text-cyan-100'
                    : 'text-slate-200 hover:bg-slate-900/70'
                }`}
                onClick={() => commit(entry)}
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{name}</span>
                  {secondary && (
                    <span className="block truncate text-[10px] text-slate-600">{secondary}</span>
                  )}
                </span>
                <span className="shrink-0 rounded-full border border-slate-700/50 bg-slate-950/60 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-500">
                  d{entry.degree}
                </span>
                <span className="shrink-0 text-[10px] tabular-nums text-slate-700">
                  #{entry.id}
                </span>
              </button>
              <a
                href={personUrl(entry.id)}
                target="_blank"
                rel="noopener noreferrer"
                className={`${subtleLink} flex items-center px-2 text-[10px] hover:bg-slate-900/70`}
                title="打开 Bangumi 人物页"
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                ↗
              </a>
            </li>
          )})}
        </ul>
      )}
    </div>
  )
}
