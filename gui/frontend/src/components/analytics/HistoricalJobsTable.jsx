function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  const totalSec = Math.round(seconds)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function formatDurationMs(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  return `${seconds.toFixed(1)}s`
}

const HistoricalJobsTable = ({ perJobStats }) => {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">Historical Jobs</h2>
      {perJobStats.length > 0 ? (
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border">
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">#</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Words</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Sent.</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Chunks</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Voice</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">LLM</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Voice Dur</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Transcribe</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Render</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Total</th>
              </tr>
            </thead>
            <tbody>
              {perJobStats.map((job, idx) => {
                const total = (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
                return (
                  <tr key={idx} className="border-b border-border/40 last:border-b-0 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-3 font-mono text-xs text-muted-foreground">{idx + 1}</td>
                    <td className="py-2 px-3">{job.word_count ?? '—'}</td>
                    <td className="py-2 px-3">{job.sentence_count ?? '—'}</td>
                    <td className="py-2 px-3">{job.chunk_count ?? '—'}</td>
                    <td className="py-2 px-3 font-mono text-xs" title={job.voice_id}>{job.voice_id ? (job.voice_id.length > 14 ? job.voice_id.slice(0, 14) + '…' : job.voice_id) : '—'}</td>
                    <td className="py-2 px-3 font-mono text-xs">{formatDurationMs(job.llm_duration)}</td>
                    <td className="py-2 px-3 font-mono text-xs">{formatDurationMs(job.voice_duration)}</td>
                    <td className="py-2 px-3 font-mono text-xs">{formatDurationMs(job.transcribe_duration)}</td>
                    <td className="py-2 px-3 font-mono text-xs">{formatDurationMs(job.render_duration)}</td>
                    <td className="py-2 px-3 font-mono text-xs font-semibold">{formatDuration(total)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
          No historical job data available.
        </div>
      )}
    </div>
  )
}

export default HistoricalJobsTable
