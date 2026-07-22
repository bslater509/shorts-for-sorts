import { useState, useEffect } from 'react'
import { BarChart3, Layers, Sparkles, Film, Clock } from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts'
import * as api from '@/lib/api'

const COLORS = ['#3b82f6', '#a855f7', '#f59e0b', '#10b981']
const PHASES = ['LLM', 'Voice', 'Transcribe', 'Render']

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

      {/* B. Phase Distribution (donut) + C. Duration by Voice (horizontal bar) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Phase Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={phaseData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, value }) => `${name} ${value}%`}
                  labelLine={false}
                >
                  {phaseData.map((entry, idx) => (
                    <Cell key={entry.name} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '13px'
                  }}
                  formatter={(value, name) => [`${value}%`, name]}
                />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Avg Duration by Voice</h2>
          {voiceDurationData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={voiceDurationData}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.4} />
                  <XAxis type="number" tick={{ fontSize: 12 }} tickFormatter={v => `${v}s`} />
                  <YAxis type="category" dataKey="voice" width={90} tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      fontSize: '13px'
                    }}
                    formatter={(value) => [`${value}s`, 'Avg Duration']}
                  />
                  <Bar dataKey="avgDuration" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
              No voice data available.
            </div>
          )}
        </div>
      </div>

      {/* D. Per-Job Duration Breakdown (stacked bar) */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Per-Job Duration Breakdown</h2>
        {stackedBarData.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stackedBarData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.4} />
                <XAxis dataKey="index" tick={{ fontSize: 12 }} label={{ value: 'Job #', position: 'insideBottomRight', offset: -5, style: { fontSize: 12, fill: 'hsl(var(--muted-foreground))' } }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `${v}s`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '13px'
                  }}
                />
                <Legend
                  verticalAlign="top"
                  iconType="rect"
                  formatter={(value) => <span className="text-sm text-foreground">{value}</span>}
                />
                <Bar dataKey="llm" stackId="a" fill="#3b82f6" name="LLM" />
                <Bar dataKey="voice" stackId="a" fill="#a855f7" name="Voice" />
                <Bar dataKey="transcribe" stackId="a" fill="#f59e0b" name="Transcribe" />
                <Bar dataKey="render" stackId="a" fill="#10b981" name="Render" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No job duration data available.
          </div>
        )}
      </div>

      {/* E. Content Complexity Table */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Content Complexity</h2>
        {complexityData.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">#</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Word Count</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Total Duration</th>
                </tr>
              </thead>
              <tbody>
                {complexityData.map((row) => (
                  <tr key={row.index} className="border-b border-border/40 last:border-b-0 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-3 font-mono text-xs">{row.index}</td>
                    <td className="py-2 px-3">{row.wordCount}</td>
                    <td className="py-2 px-3 font-mono">{formatDuration(row.totalDuration)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
            No complexity data available.
          </div>
        )}
      </div>

      {/* F. Historical Jobs Table */}
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
    </div>
  )
}
