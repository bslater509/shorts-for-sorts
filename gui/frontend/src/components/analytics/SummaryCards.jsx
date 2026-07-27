import { Layers, Sparkles, Film, BarChart3 } from 'lucide-react'

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
    key: 'totalJobs',
    label: 'Total Jobs',
    icon: Layers,
    iconWrapClass: 'bg-gradient-to-br from-blue-500/20 to-blue-500/5 border-blue-500/20',
    iconClass: 'text-blue-400',
    barClass: 'from-blue-500/40 to-transparent',
    borderGlow: 'hover:border-blue-500/20',
    shadowGlow: 'hover:shadow-blue-500/5',
  },
  {
    key: 'avgLlm',
    label: 'Avg LLM Time',
    icon: Sparkles,
    iconWrapClass: 'bg-gradient-to-br from-purple-500/20 to-purple-500/5 border-purple-500/20',
    iconClass: 'text-purple-400',
    barClass: 'from-purple-500/40 to-transparent',
    borderGlow: 'hover:border-purple-500/20',
    shadowGlow: 'hover:shadow-purple-500/5',
  },
  {
    key: 'avgVideo',
    label: 'Avg Video Time',
    icon: Film,
    iconWrapClass: 'bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 border-emerald-500/20',
    iconClass: 'text-emerald-400',
    barClass: 'from-emerald-500/40 to-transparent',
    borderGlow: 'hover:border-emerald-500/20',
    shadowGlow: 'hover:shadow-emerald-500/5',
  },
  {
    key: 'samples',
    label: 'Samples',
    icon: BarChart3,
    iconWrapClass: 'bg-gradient-to-br from-violet-500/20 to-violet-500/5 border-violet-500/20',
    iconClass: 'text-violet-400',
    barClass: 'from-violet-500/40 to-transparent',
    borderGlow: 'hover:border-violet-500/20',
    shadowGlow: 'hover:shadow-violet-500/5',
  },
]

const SummaryCards = ({ perJobStats, avgLlmDuration, avgVideoDuration, sampleCount }) => {
  const values = [
    perJobStats.length,
    avgLlmDuration != null ? formatDuration(avgLlmDuration) : '—',
    avgVideoDuration != null ? formatDuration(avgVideoDuration) : '—',
    sampleCount,
  ]

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
            <div
              className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r ${card.barClass}`}
            />

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
                <p className="text-2xl font-bold tracking-tight text-foreground">
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

export default SummaryCards
