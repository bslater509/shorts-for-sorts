import { Layers, Sparkles, Film, BarChart3 } from 'lucide-react'

function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  const totalSec = Math.round(seconds)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const SummaryCards = ({ perJobStats, avgLlmDuration, avgVideoDuration, sampleCount }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-background border border-border/50 rounded-xl p-4 shadow-sm flex items-center gap-4">
        <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <Layers size={20} className="text-blue-500" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Total Jobs</p>
          <p className="text-2xl font-bold">{perJobStats.length}</p>
        </div>
      </div>
      <div className="bg-background border border-border/50 rounded-xl p-4 shadow-sm flex items-center gap-4">
        <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20">
          <Sparkles size={20} className="text-purple-500" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Avg LLM Time</p>
          <p className="text-2xl font-bold">{avgLlmDuration != null ? formatDuration(avgLlmDuration) : '—'}</p>
        </div>
      </div>
      <div className="bg-background border border-border/50 rounded-xl p-4 shadow-sm flex items-center gap-4">
        <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <Film size={20} className="text-emerald-500" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Avg Video Time</p>
          <p className="text-2xl font-bold">{avgVideoDuration != null ? formatDuration(avgVideoDuration) : '—'}</p>
        </div>
      </div>
      <div className="bg-background border border-border/50 rounded-xl p-4 shadow-sm flex items-center gap-4">
        <div className="p-2.5 rounded-lg bg-violet-500/10 border border-violet-500/20">
          <BarChart3 size={20} className="text-violet-500" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Samples</p>
          <p className="text-2xl font-bold">{sampleCount}</p>
        </div>
      </div>
    </div>
  )
}

export default SummaryCards
