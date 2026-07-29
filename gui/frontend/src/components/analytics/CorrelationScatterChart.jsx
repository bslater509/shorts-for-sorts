import { useMemo, useState } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

const VOICE_COLORS = [
  '#8b5cf6', '#06b6d4', '#f59e0b', '#10b981',
  '#ef4444', '#ec4899', '#f97316', '#14b8a6',
  '#6366f1', '#d946ef',
]

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const data = entry.payload
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3.5 py-2.5 shadow-xl text-sm min-w-[160px]">
      <p className="font-semibold text-foreground mb-1.5 text-xs uppercase tracking-wide">Job Details</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Words</span>
          <span className="text-xs font-medium text-foreground">{data.wordCount}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Total Process</span>
          <span className="text-xs font-medium text-foreground">{data.totalDuration}s</span>
        </div>
        {data.videoDuration != null && (
          <div className="flex justify-between gap-4">
            <span className="text-xs text-muted-foreground">Video Out</span>
            <span className="text-xs font-medium text-foreground">{data.videoDuration}s</span>
          </div>
        )}
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Voice</span>
          <span className="text-xs font-medium text-foreground font-mono">{data.fullVoice || '—'}</span>
        </div>
      </div>
      {/* Mini trend insight */}
      {data.totalDuration > 0 && data.wordCount > 0 && (
        <p className="text-[10px] text-muted-foreground/50 mt-1.5 pt-1.5 border-t border-border/20">
          ~{data.wordCount > 0 ? (data.totalDuration / data.wordCount).toFixed(2) : '—'}s per word
        </p>
      )}
    </div>
  )
}

/**
 * Renders a scatter plot of Word Count vs Total Processing Duration.
 * Each dot is a single job, colored by voice ID.
 */
const CorrelationScatterChart = ({ perJobStats }) => {
  const [viewMode, setViewMode] = useState('processing') // 'processing' | 'video'

  // Prepare scatter data
  const scatterData = useMemo(() => {
    const uniqueVoices = []
    const seen = new Set()

    return perJobStats.map((job) => {
      const totalDuration = (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
      const voice = job.voice_id || 'Unknown'

      if (!seen.has(voice)) {
        seen.add(voice)
        uniqueVoices.push(voice)
      }

      return {
        wordCount: job.word_count || 0,
        totalDuration: parseFloat(totalDuration.toFixed(1)),
        videoDuration: job.video_duration != null ? parseFloat(job.video_duration.toFixed(1)) : null,
        voice,
        fullVoice: voice,
        voiceColorIdx: uniqueVoices.indexOf(voice),
      }
    })
  }, [perJobStats])

  const yKey = viewMode === 'video' ? 'videoDuration' : 'totalDuration'
  const yLabel = viewMode === 'video' ? 'Video Duration (s)' : 'Total Processing Time (s)'

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold">Word Count vs. Duration</h2>
        {/* Toggle between processing and video duration */}
        <div className="flex items-center gap-1 bg-secondary/20 rounded-lg p-0.5 border border-border/30">
          <button
            onClick={() => setViewMode('processing')}
            className={`text-[10px] font-medium px-2.5 py-1 rounded-md transition-all duration-200 ${
              viewMode === 'processing'
                ? 'bg-violet-500/20 text-violet-300 shadow-sm'
                : 'text-muted-foreground/60 hover:text-muted-foreground'
            }`}
          >
            Processing
          </button>
          <button
            onClick={() => setViewMode('video')}
            className={`text-[10px] font-medium px-2.5 py-1 rounded-md transition-all duration-200 ${
              viewMode === 'video'
                ? 'bg-violet-500/20 text-violet-300 shadow-sm'
                : 'text-muted-foreground/60 hover:text-muted-foreground'
            }`}
          >
            Video Out
          </button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        How {viewMode === 'processing' ? 'processing time' : 'video length'} scales with content length — each dot is one job, colored by voice
      </p>
      {scatterData.length > 0 ? (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart
              margin={{ top: 10, right: 20, left: 10, bottom: 20 }}
            >
              <defs>
                {VOICE_COLORS.map((color, idx) => (
                  <radialGradient key={idx} id={`dotGlow${idx}`} cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor={color} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </radialGradient>
                ))}
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.25}
              />
              <XAxis
                dataKey="wordCount"
                name="Word Count"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Word Count',
                  position: 'insideBottom',
                  offset: -10,
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
              />
              <YAxis
                dataKey={yKey}
                name={yLabel}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={v => v != null ? `${v}s` : ''}
                label={{
                  value: yLabel,
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{
                  stroke: 'hsl(var(--muted-foreground))',
                  strokeDasharray: '3 3',
                  strokeOpacity: 0.3,
                }}
              />
              <Scatter
                data={scatterData}
                shape={(props) => {
                  const { cx, cy, payload } = props
                  const color = VOICE_COLORS[payload.voiceColorIdx % VOICE_COLORS.length]
                  return (
                    <g>
                      {/* Glow ring */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={10}
                        fill={`url(#dotGlow${payload.voiceColorIdx % VOICE_COLORS.length})`}
                        style={{ pointerEvents: 'none' }}
                      />
                      {/* Dot */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={color}
                        stroke="hsl(var(--background))"
                        strokeWidth={1.5}
                        style={{
                          filter: 'drop-shadow(0 0 4px rgba(139, 92, 246, 0.25))',
                          transition: 'all 0.2s ease-out',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => {
                          e.target.setAttribute('r', '9')
                          e.target.style.filter = `drop-shadow(0 0 8px ${color}66)`
                        }}
                        onMouseLeave={(e) => {
                          e.target.setAttribute('r', '6')
                          e.target.style.filter = 'drop-shadow(0 0 4px rgba(139, 92, 246, 0.25))'
                        }}
                      />
                    </g>
                  )
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>Not enough data for correlation analysis.</p>
            <p className="text-xs opacity-60">Run more jobs to populate the scatter plot.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default CorrelationScatterChart
