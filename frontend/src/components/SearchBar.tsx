import { useState, useCallback, useRef, useEffect } from 'react'
import { searchPersons } from '../data/loader'
import { personUrl } from '../data/links'
import { displayPersonName, secondaryPersonName } from '../data/personNames'
import type { PersonNameMode, SearchEntry } from '../types'
import { ExternalLink, Search, X } from 'lucide-react'
import { iconButton, panelShell } from './ui'

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
            <span className="block truncate text-sm text-zinc-100">{selectedName}</span>
            {selectedSecondary && (
              <span className="block truncate text-xs text-zinc-500">{selectedSecondary}</span>
            )}
          </span>
          <a
            href={personUrl(selectedEntry.id)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className={iconButton}
            title="打开 Bangumi 人物页"
          >
            <ExternalLink size={14} />
          </a>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleClear() }}
            className={iconButton}
            title="清除"
          >
            <X size={15} />
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
      <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => { if (results.length > 0) setOpen(true) }}
        onKeyDown={handleKeyDown}
        placeholder="搜索人名或 Bangumi ID"
        className={`${panelShell} w-full py-2 pl-8 pr-3 text-sm text-zinc-100 outline-none transition-colors placeholder:text-zinc-500 focus:border-[#f5c76b]/60`}
        autoComplete="off"
      />
      {loading && query.length >= 1 && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="h-3.5 w-3.5 animate-spin rounded-full border border-zinc-500 border-t-transparent" />
        </div>
      )}
      {open && results.length > 0 && (
        <ul className={`${panelShell} absolute top-full z-50 mt-1 max-h-80 w-full overflow-y-auto py-1`}>
          {results.map((entry, idx) => {
            const name = displayPersonName(entry, personNameMode)
            const secondary = secondaryPersonName(entry, personNameMode)
            return (
            <li key={entry.id} className="flex items-stretch">
              <button
                className={`flex min-w-0 flex-1 items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors ${
                  idx === selectedIdx ? 'bg-white/[0.07] text-zinc-50' : 'text-zinc-200'
                }`}
                onClick={() => commit(entry)}
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{name}</span>
                  {secondary && (
                    <span className="block truncate text-xs text-zinc-500">{secondary}</span>
                  )}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-zinc-500">
                  {entry.degree} 位合作者
                </span>
              </button>
              <a
                href={personUrl(entry.id)}
                target="_blank"
                rel="noopener noreferrer"
                className={`${iconButton} my-auto mr-1`}
                title="打开 Bangumi 人物页"
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                <ExternalLink size={14} />
              </a>
            </li>
          )})}
        </ul>
      )}
    </div>
  )
}
