import { Zap, Brain, Clock, Film } from 'lucide-react'

function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  const totalSec = Math.round(seconds)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const cardConfigs = [
  {
    key: 'genSpeed',
    label: 'Gen Speed Ratio',
    icon: Zap,
    iconWrapClass: 'bg-gradient-to-br from-amber-500/20 to-amber-500/5 border-amber-500/20',
    iconClass: 'text-amber-400',
    barClass: 'from-amber-500/40 to-transparent',
    borderGlow: 'hover:border-amber-500/20',
    shadowGlow: 'hover:shadow-amber-500/5',
  },
  {
    key: 'llmSpeed',
    label: 'LLM Speed',
    icon: Brain,
    iconWrapClass: 'bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 border-cyan-500/20',
    iconClass: 'text-cyan-400',
    barClass: 'from-cyan-500/40 to-transparent',
    borderGlow: 'hover:border-cyan-500/20',
    shadowGlow: 'hover:shadow-cyan-500/5',
  },
  {
    key: 'avgProcessing',
    label: 'Avg Processing',
    icon: Clock,
    iconWrapClass: 'bg-gradient-to-br from-rose-500/20 to-rose-500/5 border-rose-500/20',
    iconClass: 'text-rose-400',
    barClass: 'from-rose-500/40 to-transparent',
    borderGlow: 'hover:border-rose-500/20',
    shadowGlow: 'hover:shadow-rose-500/5',
  },
  {
    key: 'totalVideo',
    label: 'Total Video',
    icon: Film,
    iconWrapClass: 'bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 border-emerald-500/20',
    iconClass: 'text-emerald-400',
    barClass: 'from-emerald-500/40 to-transparent',
    borderGlow: 'hover:border-emerald-500/20',
    shadowGlow: 'hover:shadow-emerald-500/5',
  },
]

const EfficiencyMetrics = ({ perJobStats }) => {
  const totalVideoDuration = perJobStats.reduce((sum, job) => sum + (job.video_duration || 0), 0)
  const totalProcessingDuration = perJobStats.reduce((sum, job) => {
    return sum + (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
  }, 0)
  const totalWords = perJobStats.reduce((sum, job) => sum + (job.word_count || 0), 0)
  const totalLlmDuration = perJobStats.reduce((sum, job) => sum + (job.llm_duration || 0), 0)

  const genSpeedRatio = totalProcessingDuration > 0
    ? (totalVideoDuration / totalProcessingDuration).toFixed(2) + 'x'
    : '—'

  const llmSpeed = totalLlmDuration > 0
    ? (totalWords / totalLlmDuration).toFixed(1) + ' w/s'
    : '—'

  const avgProcessing = perJobStats.length > 0
    ? formatDuration(totalProcessingDuration / perJobStats.length)
    : '—'

  const totalVideo = totalVideoDuration > 0
    ? formatDuration(totalVideoDuration)
    : '—'

  const values = [genSpeedRatio, llmSpeed, avgProcessing, totalVideo]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cardConfigs.map((card, idx) => {
        const Icon = card.icon
        const value = values[idx]
        return (
          <div
            key={card.key}
            className={`
              group relative bg-card border border-border/50 rounded-xl p-5
              shadow-sm overflow-hidden transition-all duration-300 ease-out
              hover:scale-[1.03] hover:shadow-xl cursor-default
              ${card.borderGlow} ${card.shadowGlow}
            `}
          >
            {/* Accent bar at top */}
            <div className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r ${card.barClass}`} />

            <div className="flex items-center gap-4">
              {/* Icon with gradient background */}
              <div
                className={`
                  relative p-3 rounded-xl backdrop-blur-sm
                  border transition-all duration-300 ease-out
                  group-hover:scale-110 group-hover:rotate-[4deg] group-hover:shadow-lg
                  ${card.iconWrapClass}
                `}
              >
                <Icon size={20} className={card.iconClass} />
              </div>

              {/* Text */}
              <div className="min-w-0">
                <p className="text-[10px] text-muted-foreground font-semibold uppercase tracking-[0.12em] mb-0.5">
                  {card.label}
                </p>
                <p className="text-xl font-bold tracking-tight text-foreground">
                  {value}
                </p>
              </div>
            </div>

            {/* Subtle corner decoration */}
            <div className="absolute -top-3 -right-3 w-12 h-12 bg-gradient-to-br from-white/[0.02] to-transparent rounded-full blur-xl pointer-events-none" />
          </div>
        )
      })}
    </div>
  )
}

export default EfficiencyMetrics
