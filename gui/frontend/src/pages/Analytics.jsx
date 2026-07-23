import { useState, useEffect } from 'react'
import { BarChart3 } from 'lucide-react'
import * as api from '@/lib/api'
import SummaryCards from '@/components/analytics/SummaryCards'
import PhaseDistributionChart from '@/components/analytics/PhaseDistributionChart'
import DurationByVoiceChart from '@/components/analytics/DurationByVoiceChart'
import PerJobBreakdownChart from '@/components/analytics/PerJobBreakdownChart'
import ComplexityTable from '@/components/analytics/ComplexityTable'
import HistoricalJobsTable from '@/components/analytics/HistoricalJobsTable'

const PHASES = ['LLM', 'Voice', 'Transcribe', 'Render']

export default function Analytics() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const fetchStats = async () => {
      try {
        const data = await api.getBatchStats()
        if (!cancelled) {
          setStats(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchStats()
    return () => { cancelled = true }
  }, [])

  const perJobStats = stats?.per_job_stats || []
  const sampleCount = stats?.sample_count || 0
  const avgLlmDuration = stats?.avg_llm_duration
  const avgVideoDuration = stats?.avg_video_duration
  const phaseRatios = stats?.phase_ratios || {}

  // Phase distribution data for pie chart
  const phaseData = PHASES.map(phase => ({
    name: phase,
    value: phaseRatios[phase] != null ? Math.round(phaseRatios[phase] * 100) : 0
  }))

  // Duration by voice (group + average)
  const voiceMap = {}
  perJobStats.forEach(job => {
    const voice = job.voice_id || 'Unknown'
    if (!voiceMap[voice]) voiceMap[voice] = { total: 0, count: 0 }
    voiceMap[voice].total += (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
    voiceMap[voice].count += 1
  })
  const voiceDurationData = Object.entries(voiceMap).map(([voice, { total, count }]) => ({
    voice: voice.length > 20 ? voice.slice(0, 20) + '…' : voice,
    avgDuration: parseFloat((total / count).toFixed(1))
  }))

  // Per-job stacked bar data
  const stackedBarData = perJobStats.map((job, idx) => ({
    index: idx + 1,
    wordCount: job.word_count || 0,
    llm: parseFloat((job.llm_duration || 0).toFixed(1)),
    voice: parseFloat((job.voice_duration || 0).toFixed(1)),
    transcribe: parseFloat((job.transcribe_duration || 0).toFixed(1)),
    render: parseFloat((job.render_duration || 0).toFixed(1))
  }))

  // Content complexity table data
  const complexityData = perJobStats.map((job, idx) => ({
    index: idx + 1,
    wordCount: job.word_count || 0,
    totalDuration: ((job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0))
  }))

  if (loading) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="animate-pulse bg-secondary/40 rounded-xl h-24" />
          ))}
        </div>
        <div className="animate-pulse bg-secondary/40 rounded-xl h-80" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </header>
        <div className="bg-card border border-border rounded-xl p-12 flex flex-col items-center justify-center text-center text-muted-foreground space-y-3">
          <BarChart3 size={48} className="opacity-20" />
          <p>Failed to load analytics data.</p>
          <p className="text-sm text-red-400">{error}</p>
        </div>
      </div>
    )
  }

  if (!stats || perJobStats.length === 0) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto">
        <header className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </header>
        <div className="bg-card border border-border rounded-xl p-12 flex flex-col items-center justify-center text-center text-muted-foreground space-y-3">
          <BarChart3 size={48} className="opacity-20" />
          <p>No batch statistics available yet.</p>
          <p className="text-sm">Run a batch to see analytics here.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto">
      <header className="flex flex-col sm:flex-row items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="text-violet-500" />
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">Historical batch statistics and performance insights.</p>
        </div>
      </header>

      {/* A. Summary Cards */}
      <SummaryCards
        perJobStats={perJobStats}
        avgLlmDuration={avgLlmDuration}
        avgVideoDuration={avgVideoDuration}
        sampleCount={sampleCount}
      />

      {/* B. Phase Distribution + C. Duration by Voice */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhaseDistributionChart phaseData={phaseData} />
        <DurationByVoiceChart voiceDurationData={voiceDurationData} />
      </div>

      {/* D. Per-Job Duration Breakdown */}
      <PerJobBreakdownChart stackedBarData={stackedBarData} />

      {/* E. Content Complexity Table */}
      <ComplexityTable complexityData={complexityData} />

      {/* F. Historical Jobs Table */}
      <HistoricalJobsTable perJobStats={perJobStats} />
    </div>
  )
}
