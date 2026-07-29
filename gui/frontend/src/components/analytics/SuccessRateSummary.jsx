import { useMemo } from 'react'
import { CircleCheck, CircleX, BookText, List } from 'lucide-react'

const cardConfigs = [
  {
    key: 'successRate',
    label: 'Success Rate',
    icon: CircleCheck,
    iconClass: 'text-emerald-400',
    barClass: 'from-emerald-500/40 to-transparent',
    format: (v) => `${v}%`,
  },
  {
    key: 'totalFailed',
    label: 'Total Failed',
    icon: CircleX,
    iconClass: 'text-rose-400',
    barClass: 'from-rose-500/40 to-transparent',
    format: (v) => `${v}`,
  },
  {
    key: 'avgWordsPerSentence',
    label: 'Avg Words/Sentence',
    icon: BookText,
    iconClass: 'text-amber-400',
    barClass: 'from-amber-500/40 to-transparent',
    format: (v) => `${v.toFixed(1)}`,
  },
  {
    key: 'totalJobs',
    label: 'Total Jobs',
    icon: List,
    iconClass: 'text-blue-400',
    barClass: 'from-blue-500/40 to-transparent',
    format: (v) => `${v}`,
  },
]

const SuccessRateSummary = ({ perJobStats = [] }) => {
  const metrics = useMemo(() => {
    const total = perJobStats.length
    if (total === 0) {
      return { successRate: 0, totalFailed: 0, avgWordsPerSentence: 0, totalJobs: 0 }
    }

    let successCount = 0
    let failedCount = 0
    let totalWords = 0
    let totalSentences = 0

    perJobStats.forEach(job => {
      const status = job.status
      // Missing status (old data) counts as success
      if (!status || status === 'success') {
        successCount++
      } else if (status === 'failed') {
        failedCount++
      }
      totalWords += job.word_count || 0
      totalSentences += job.sentence_count || 0
    })

    const successRate = total > 0 ? Math.round((successCount / total) * 100) : 0
    const avgWordsPerSentence = totalSentences > 0
      ? parseFloat((totalWords / totalSentences).toFixed(1))
      : 0

    return { successRate, totalFailed: failedCount, avgWordsPerSentence, totalJobs: total }
  }, [perJobStats])

  const values = [
    metrics.successRate,
    metrics.totalFailed,
    metrics.avgWordsPerSentence,
    metrics.totalJobs,
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cardConfigs.map((card, idx) => {
        const Icon = card.icon
        const value = values[idx]
        return (
          <div
            key={card.key}
            className="group relative bg-card border border-border/50 rounded-xl p-5 shadow-sm overflow-hidden transition-all duration-300 ease-out hover:scale-[1.03] hover:shadow-xl cursor-default"
          >
            {/* Accent bar at top */}
            <div className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r ${card.barClass}`} />

            <div className="flex items-center gap-4">
              {/* Icon */}
              <div className="relative p-3 rounded-xl bg-gradient-to-br from-white/[0.04] to-transparent border border-border/20 transition-all duration-300 ease-out group-hover:scale-110 group-hover:rotate-[4deg] group-hover:shadow-lg">
                <Icon size={20} className={card.iconClass} />
              </div>

              {/* Text */}
              <div className="min-w-0">
                <p className="text-[10px] text-muted-foreground font-semibold uppercase tracking-[0.12em] mb-0.5">
                  {card.label}
                </p>
                <p className="text-2xl font-bold tracking-tight text-foreground">
                  {card.format(value)}
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

export default SuccessRateSummary
