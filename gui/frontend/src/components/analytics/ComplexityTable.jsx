import { useState } from 'react'

function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  const totalSec = Math.round(seconds)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const InlineDurationBar = ({ value, max }) => {
  if (max === 0) return null
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <span className="font-mono text-xs tabular-nums text-foreground shrink-0 w-12 text-right">
        {formatDuration(value)}
      </span>
      <div className="flex-1 h-1.5 bg-secondary/20 rounded-full overflow-hidden min-w-[32px] max-w-[72px]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-purple-500/40 to-purple-500/70 transition-all duration-500 ease-out"
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
    </div>
  )
}

const ComplexityTable = ({ complexityData }) => {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sortedData = [...complexityData]
  if (sortKey) {
    sortedData.sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }

  const maxDuration = sortedData.length > 0
    ? Math.max(...sortedData.map(d => d.totalDuration))
    : 0

  const renderSortArrow = (key) => {
    if (sortKey !== key) return null
    return <span className="ml-1 text-[9px]">{sortDir === 'asc' ? '▲' : '▼'}</span>
  }

  const thClass = "sticky top-0 z-10 text-left py-3 px-4 text-muted-foreground font-semibold text-[10px] uppercase tracking-[0.12em] cursor-pointer select-none hover:text-foreground/80 transition-colors"

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Content Complexity</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Word count vs total processing duration per job
      </p>
      {sortedData.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/60 bg-secondary/10">
                <th className={thClass} onClick={() => handleSort('index')}>
                  #{renderSortArrow('index')}
                </th>
                <th className={thClass} onClick={() => handleSort('wordCount')}>
                  Word Count{renderSortArrow('wordCount')}
                </th>
                <th className={thClass} onClick={() => handleSort('emojiCount')}>
                  Emojis{renderSortArrow('emojiCount')}
                </th>
                <th className={thClass} onClick={() => handleSort('totalDuration')}>
                  Total Duration{renderSortArrow('totalDuration')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedData.map((row, idx) => (
                <tr
                  key={row.index}
                  className={`
                    border-b border-border/20 last:border-b-0
                    transition-colors duration-150
                    hover:bg-secondary/20
                    ${idx % 2 === 1 ? 'bg-secondary/5' : 'bg-transparent'}
                  `}
                >
                  <td className="py-2.5 px-4 font-mono text-[11px] text-muted-foreground/60">
                    {idx + 1}
                  </td>
                  <td className="py-2.5 px-4">
                    <span className="tabular-nums text-sm font-medium text-foreground">
                      {row.wordCount}
                    </span>
                  </td>
                  <td className="py-2.5 px-4">
                    <span className="tabular-nums text-sm font-medium text-foreground">
                      {row.emojiCount ?? '—'}
                    </span>
                  </td>
                  <td className="py-2.5 px-4">
                    <InlineDurationBar value={row.totalDuration} max={maxDuration} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No complexity data available.</p>
            <p className="text-xs opacity-60">Complexity analysis appears once jobs are processed.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ComplexityTable
