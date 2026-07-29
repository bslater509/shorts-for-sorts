import { useState } from 'react'

function formatDurationMs(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  return `${seconds.toFixed(1)}s`
}

const DURATION_KEYS = ['llm_duration', 'voice_duration', 'transcribe_duration', 'render_duration']

const InlineMiniBar = ({ value, max, color }) => {
  if (max === 0 || value == null) return null
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <div className="w-10 shrink-0 text-right">
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {formatDurationMs(value)}
        </span>
      </div>
      <div className="flex-1 h-1 bg-secondary/20 rounded-full overflow-hidden min-w-[20px] max-w-[44px]">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

const VoiceTooltip = ({ voiceId }) => {
  if (!voiceId || voiceId.length <= 14) return <span className="font-mono text-[11px] text-muted-foreground">{voiceId || '—'}</span>
  return (
    <span
      className="font-mono text-[11px] text-muted-foreground border-b border-dotted border-muted-foreground/30 cursor-help"
      title={voiceId}
    >
      {voiceId.slice(0, 14) + '…'}
    </span>
  )
}

const HistoricalJobsTable = ({ perJobStats }) => {
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

  // Sort data — attach original index for 'index' sort key
  const sorted = [...perJobStats].map((job, idx) => ({ ...job, _originalIndex: idx }))
  if (sortKey) {
    sorted.sort((a, b) => {
      let aVal, bVal
      if (sortKey === 'index') {
        aVal = a._originalIndex
        bVal = b._originalIndex
      } else if (sortKey === 'total') {
        aVal = (a.llm_duration || 0) + (a.voice_duration || 0) + (a.transcribe_duration || 0) + (a.render_duration || 0)
        bVal = (b.llm_duration || 0) + (b.voice_duration || 0) + (b.transcribe_duration || 0) + (b.render_duration || 0)
      } else if (sortKey === 'voice_id') {
        aVal = (a.voice_id || '').toLowerCase()
        bVal = (b.voice_id || '').toLowerCase()
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      } else {
        aVal = a[sortKey] || 0
        bVal = b[sortKey] || 0
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }

  // Compute max per duration column for inline bars (from sorted data)
  const maxByKey = {}
  DURATION_KEYS.forEach((key) => {
    maxByKey[key] = sorted.length > 0
      ? Math.max(...sorted.map(j => j[key] || 0))
      : 0
  })
  maxByKey.video_duration = sorted.length > 0
    ? Math.max(...sorted.map(j => j.video_duration || 0))
    : 0
  const maxTotal = sorted.length > 0
    ? Math.max(...sorted.map(j =>
        (j.llm_duration || 0) + (j.voice_duration || 0) +
        (j.transcribe_duration || 0) + (j.render_duration || 0)
      ))
    : 0

  const COLUMN_COLORS = {
    llm_duration: '#3b82f6',
    voice_duration: '#a855f7',
    transcribe_duration: '#f59e0b',
    render_duration: '#10b981',
    video_duration: '#8b5cf6',
  }

  const renderSortArrow = (key) => {
    if (sortKey !== key) return null
    return <span className="ml-1 text-[9px]">{sortDir === 'asc' ? '▲' : '▼'}</span>
  }

  const thClass = "text-left py-3 px-3 text-muted-foreground font-semibold text-[10px] uppercase tracking-[0.12em] whitespace-nowrap cursor-pointer select-none hover:text-foreground/80 transition-colors"

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Historical Jobs</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Detailed per-job breakdown with timing for each processing phase
      </p>
      {sorted.length > 0 ? (
        <div
          className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-border/30
            [&::-webkit-scrollbar]:w-1.5
            [&::-webkit-scrollbar]:h-1.5
            [&::-webkit-scrollbar-track]:bg-transparent
            [&::-webkit-scrollbar-thumb]:bg-secondary/40
            [&::-webkit-scrollbar-thumb]:rounded-full
            [&::-webkit-scrollbar-thumb]:hover:bg-secondary/60"
        >
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="border-b border-border/60 bg-card shadow-sm">
                <th className={thClass} onClick={() => handleSort('index')}>#{renderSortArrow('index')}</th>
                <th className={thClass} onClick={() => handleSort('word_count')}>Words{renderSortArrow('word_count')}</th>
                <th className={thClass} onClick={() => handleSort('sentence_count')}>Sent.{renderSortArrow('sentence_count')}</th>
                <th className={thClass} onClick={() => handleSort('chunk_count')}>Chunks{renderSortArrow('chunk_count')}</th>
                <th className={thClass} onClick={() => handleSort('voice_id')}>Voice{renderSortArrow('voice_id')}</th>
                <th className={thClass} onClick={() => handleSort('model')}>Model{renderSortArrow('model')}</th>
                <th className={thClass} onClick={() => handleSort('layout')}>Layout{renderSortArrow('layout')}</th>
                <th className={thClass} onClick={() => handleSort('status')}>Status{renderSortArrow('status')}</th>
                <th className={thClass} onClick={() => handleSort('llm_duration')}>LLM{renderSortArrow('llm_duration')}</th>
                <th className={thClass} onClick={() => handleSort('voice_duration')}>Voice Dur{renderSortArrow('voice_duration')}</th>
                <th className={thClass} onClick={() => handleSort('transcribe_duration')}>Transcribe{renderSortArrow('transcribe_duration')}</th>
                <th className={thClass} onClick={() => handleSort('render_duration')}>Render{renderSortArrow('render_duration')}</th>
                <th className={thClass} onClick={() => handleSort('video_duration')}>Video{renderSortArrow('video_duration')}</th>
                <th className={thClass} onClick={() => handleSort('total')}>Total{renderSortArrow('total')}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((job, idx) => {
                const total = (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
                return (
                  <tr
                    key={idx}
                    className={`
                      border-b border-border/20 last:border-b-0
                      transition-colors duration-150
                      hover:bg-secondary/20
                      ${idx % 2 === 1 ? 'bg-secondary/5' : 'bg-transparent'}
                    `}
                  >
                    <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground/60">{idx + 1}</td>
                    <td className="py-2 px-3 text-sm tabular-nums text-foreground">{job.word_count ?? <span className="text-muted-foreground/40">—</span>}</td>
                    <td className="py-2 px-3 text-sm tabular-nums text-foreground">{job.sentence_count ?? <span className="text-muted-foreground/40">—</span>}</td>
                    <td className="py-2 px-3 text-sm tabular-nums text-foreground">{job.chunk_count ?? <span className="text-muted-foreground/40">—</span>}</td>
                    <td className="py-2 px-3">
                      <VoiceTooltip voiceId={job.voice_id} />
                    </td>
                    <td className="py-2 px-3 text-[11px] text-muted-foreground font-mono max-w-[80px] truncate" title={job.model || ''}>
                      {job.model || <span className="text-muted-foreground/40">—</span>}
                    </td>
                    <td className="py-2 px-3">
                      {job.layout ? (
                        <span className="text-[11px] font-medium text-muted-foreground bg-secondary/20 rounded-md px-2 py-0.5">
                          {job.layout === 'Split-Screen' ? 'Split' : 'Full'}
                        </span>
                      ) : (
                        <span className="text-muted-foreground/40">—</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {job.status === 'failed' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-500/10 rounded-md px-2 py-0.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                          Failed
                        </span>
                      ) : job.status === 'success' || !job.status ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 rounded-md px-2 py-0.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          OK
                        </span>
                      ) : (
                        <span className="text-muted-foreground/40">—</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={job.llm_duration} max={maxByKey.llm_duration} color={COLUMN_COLORS.llm_duration} />
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={job.voice_duration} max={maxByKey.voice_duration} color={COLUMN_COLORS.voice_duration} />
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={job.transcribe_duration} max={maxByKey.transcribe_duration} color={COLUMN_COLORS.transcribe_duration} />
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={job.render_duration} max={maxByKey.render_duration} color={COLUMN_COLORS.render_duration} />
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={job.video_duration} max={maxByKey.video_duration} color={COLUMN_COLORS.video_duration} />
                    </td>
                    <td className="py-2 px-3">
                      <InlineMiniBar value={total} max={maxTotal} color="#8b5cf6" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No historical job data available.</p>
            <p className="text-xs opacity-60">Run a batch to populate the job history.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default HistoricalJobsTable
