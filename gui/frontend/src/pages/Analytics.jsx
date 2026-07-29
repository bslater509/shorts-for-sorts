import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { BarChart3, RefreshCw, RotateCcw, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as api from '@/lib/api'
import SummaryCards from '@/components/analytics/SummaryCards'
import PhaseDistributionChart from '@/components/analytics/PhaseDistributionChart'
import DurationByVoiceChart from '@/components/analytics/DurationByVoiceChart'
import PerJobBreakdownChart from '@/components/analytics/PerJobBreakdownChart'
import ComplexityTable from '@/components/analytics/ComplexityTable'
import HistoricalJobsTable from '@/components/analytics/HistoricalJobsTable'

const PHASES = ['LLM', 'Voice', 'Transcribe', 'Render']

// Helper to format a relative time string
function timeAgo(date) {
  const diff = Date.now() - date.getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 10) return 'just now'
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  return `${Math.floor(min / 60)}h ago`
}

// Staggered wrapper — delays children entry based on index
function StaggerSection({ index, children }) {
  return (
    <div
      className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards"
      style={{ animationDelay: `${index * 120}ms` }}
    >
      {children}
    </div>
  )
}

export default function Analytics() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const fetchedAtRef = useRef(null)
  const [timeAgoLabel, setTimeAgoLabel] = useState('')

  const fetchStats = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const data = await api.getBatchStats()
      setStats(data)
      fetchedAtRef.current = new Date()
      setTimeAgoLabel('just now')
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  // Update the "time ago" label every 10s
  useEffect(() => {
    if (!fetchedAtRef.current) return
    const interval = setInterval(() => {
      setTimeAgoLabel(timeAgo(fetchedAtRef.current))
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const perJobStats = stats?.per_job_stats || []
  const sampleCount = stats?.sample_count || 0
  const avgLlmDuration = stats?.avg_llm_duration
  const avgVideoDuration = stats?.avg_video_duration
  const phaseRatios = stats?.phase_ratios || {}

  // Phase distribution data for pie chart
  const phaseData = useMemo(() =>
    PHASES.map(phase => ({
      name: phase,
      value: phaseRatios[phase] != null ? Math.round(phaseRatios[phase] * 100) : 0,
    })),
    [phaseRatios]
  )

  // Duration by voice (group + average)
  const voiceDurationData = useMemo(() => {
    const voiceMap = {}
    perJobStats.forEach(job => {
      const voice = job.voice_id || 'Unknown'
      if (!voiceMap[voice]) voiceMap[voice] = { total: 0, count: 0 }
      voiceMap[voice].total += (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
      voiceMap[voice].count += 1
    })
    return Object.entries(voiceMap).map(([voice, { total, count }]) => ({
      voice: voice.length > 20 ? voice.slice(0, 20) + '…' : voice,
      avgDuration: parseFloat((total / count).toFixed(1)),
    }))
  }, [perJobStats])

  // Per-job stacked bar data
  const stackedBarData = useMemo(() =>
    perJobStats.map((job, idx) => ({
      index: idx + 1,
      wordCount: job.word_count || 0,
      llm: parseFloat((job.llm_duration || 0).toFixed(1)),
      voice: parseFloat((job.voice_duration || 0).toFixed(1)),
      transcribe: parseFloat((job.transcribe_duration || 0).toFixed(1)),
      render: parseFloat((job.render_duration || 0).toFixed(1)),
    })),
    [perJobStats]
  )

  // Content complexity table data
  const complexityData = useMemo(() =>
    perJobStats.map((job, idx) => ({
      index: idx + 1,
      wordCount: job.word_count || 0,
      emojiCount: job.emoji_count ?? 0,
      totalDuration: ((job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)),
    })),
    [perJobStats]
  )

  // CSV export handler
  const handleDownloadCsv = useCallback(() => {
    const headers = ['#', 'Word Count', 'Sentences', 'Chunks', 'Emojis', 'Voice ID', 'LLM (s)', 'Voice (s)', 'Transcribe (s)', 'Render (s)', 'Video (s)', 'Total (s)']
    const rows = perJobStats.map((job, idx) => {
      const total = (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
      return [
        idx + 1,
        job.word_count ?? '',
        job.sentence_count ?? '',
        job.chunk_count ?? '',
        job.emoji_count ?? '',
        job.voice_id ?? '',
        (job.llm_duration ?? 0).toFixed(1),
        (job.voice_duration ?? 0).toFixed(1),
        (job.transcribe_duration ?? 0).toFixed(1),
        (job.render_duration ?? 0).toFixed(1),
        (job.video_duration ?? 0).toFixed(1),
        total.toFixed(1),
      ]
    })
    const csvContent = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `analytics-export-${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [perJobStats])

  // ---- Loading State ----
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                <BarChart3 className="text-violet-500" />
                Analytics
              </h1>
              <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
            </div>
          </div>
        </header>

        {/* Skeleton cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-card border border-border/50 rounded-xl p-5 overflow-hidden">
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 rounded-xl bg-secondary/30 animate-pulse" />
                <div className="flex-1 space-y-2">
                  <div className="h-2.5 w-16 bg-secondary/30 animate-pulse rounded" />
                  <div className="h-6 w-20 bg-secondary/30 animate-pulse rounded" />
                </div>
              </div>
              {/* Accent bar skeleton */}
              <div className="absolute inset-x-0 top-0 h-[3px] bg-secondary/20 animate-pulse" />
            </div>
          ))}
        </div>

        {/* Skeleton chart */}
        <div className="bg-card border border-border/50 rounded-xl p-6 overflow-hidden">
          <div className="h-4 w-36 bg-secondary/30 animate-pulse rounded mb-3" />
          <div className="h-3 w-56 bg-secondary/20 animate-pulse rounded mb-4" />
          <div className="h-64 bg-secondary/20 animate-pulse rounded-lg" />
        </div>
      </div>
    )
  }

  // ---- Error State ----
  if (error) {
    return (
      <div className="max-w-6xl mx-auto">
        <header className="animate-in fade-in slide-in-from-bottom-4 duration-500 mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </header>

        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:150ms]">
          <div className="bg-card border border-border/60 rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
            <div className="p-4 rounded-full bg-destructive/10 border border-destructive/20">
              <BarChart3 size={36} className="text-destructive/60" />
            </div>
            <div>
              <p className="text-lg font-semibold text-foreground mb-1">Failed to load analytics</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                The server returned an error. This might be a temporary issue or the batch API may be unavailable.
              </p>
            </div>
            <p className="text-xs text-destructive/70 bg-destructive/5 rounded-md px-3 py-1.5 font-mono max-w-lg truncate">
              {error}
            </p>
            <Button
              onClick={() => fetchStats()}
              variant="outline"
              className="text-primary hover:text-primary/80 bg-primary/10 hover:bg-primary/15 border-primary/20"
            >
              <RotateCcw size={14} />
              Retry
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // ---- Empty State ----
  if (!stats || perJobStats.length === 0) {
    return (
      <div className="max-w-6xl mx-auto">
        <header className="animate-in fade-in slide-in-from-bottom-4 duration-500 mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </header>

        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:150ms]">
          <div className="bg-card border border-border/60 rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
            <div className="p-4 rounded-full bg-secondary/20 border border-border/30">
              <BarChart3 size={36} className="text-muted-foreground/40" />
            </div>
            <div>
              <p className="text-lg font-semibold text-foreground mb-1">No data yet</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Batch statistics will appear here once you run your first batch of jobs.
                Head over to the Batch page to get started.
              </p>
            </div>
            <a
              href="/batch"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors bg-primary/10 hover:bg-primary/15 rounded-lg px-4 py-2 border border-primary/20"
            >
              Go to Batch
            </a>
          </div>
        </div>
      </div>
    )
  }

  // ---- Data State ----
  const sections = [
    { id: 'summary', component: (
      <SummaryCards
        perJobStats={perJobStats}
        avgLlmDuration={avgLlmDuration}
        avgVideoDuration={avgVideoDuration}
        sampleCount={sampleCount}
      />
    )},
    { id: 'charts', component: (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhaseDistributionChart phaseData={phaseData} />
        <DurationByVoiceChart voiceDurationData={voiceDurationData} />
      </div>
    )},
    { id: 'breakdown', component: <PerJobBreakdownChart stackedBarData={stackedBarData} /> },
    { id: 'complexity', component: <ComplexityTable complexityData={complexityData} /> },
    { id: 'history', component: <HistoricalJobsTable perJobStats={perJobStats} /> },
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <header className="animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <BarChart3 className="text-violet-500" />
              Analytics
            </h1>
            <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
          </div>

          {/* Refresh indicator */}
          {fetchedAtRef.current && (
            <div className="flex items-center gap-3 self-end sm:self-auto">
              <span className="text-[11px] text-muted-foreground/60 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 animate-pulse" />
                Updated {timeAgoLabel}
              </span>
              <Button
                onClick={() => fetchStats(true)}
                disabled={refreshing}
                variant="ghost"
                size="icon"
                className="text-muted-foreground/40 hover:text-primary"
                title="Refresh data"
              >
                <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              </Button>
              <Button
                onClick={handleDownloadCsv}
                variant="ghost"
                size="icon"
                className="text-muted-foreground/40 hover:text-primary"
                title="Download CSV"
              >
                <Download size={14} />
              </Button>
            </div>
          )}
        </div>

        {/* Decorative gradient line under header */}
        <div className="mt-4 h-px bg-gradient-to-r from-primary/30 via-primary/10 to-transparent" />
      </header>

      {/* Sections with staggered entry */}
      {sections.map((section, idx) => (
        <StaggerSection key={section.id} index={idx}>
          {section.component}
        </StaggerSection>
      ))}
    </div>
  )
}
