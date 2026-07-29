import { useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const data = entry.payload
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1">Job #{label}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Total Duration</span>
          <span className="text-xs font-medium text-foreground">{data.totalDuration.toFixed(1)}s</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Word Count</span>
          <span className="text-xs font-medium text-foreground">{data.wordCount}</span>
        </div>
      </div>
    </div>
  )
}

const DurationTrendChart = ({ perJobStats = [] }) => {
  const trendData = useMemo(() => {
    const filtered = perJobStats.filter(job => job.status !== 'failed')
    if (filtered.length === 0) return []

    return filtered.map((job, idx) => {
      const totalDuration = (job.llm_duration || 0)
        + (job.voice_duration || 0)
        + (job.transcribe_duration || 0)
        + (job.render_duration || 0)

      return {
        jobIndex: idx + 1,
        totalDuration: parseFloat(totalDuration.toFixed(1)),
        wordCount: job.word_count || 0,
        sentenceCount: job.sentence_count || 0,
      }
    })
  }, [perJobStats])

  const average =
    trendData.length > 0
      ? parseFloat((trendData.reduce((s, d) => s + d.totalDuration, 0) / trendData.length).toFixed(1))
      : 0

  const hasData = trendData.length > 0

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Processing Time Trend</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Total processing time per job across the batch sequence
      </p>
      {hasData ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={trendData}
              margin={{ top: 10, right: 20, left: 0, bottom: 5 }}
            >
              <defs>
                <linearGradient id="durationGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                vertical={false}
              />
              <XAxis
                dataKey="jobIndex"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
                label={{
                  value: 'Job #',
                  position: 'insideBottom',
                  offset: -8,
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={v => `${v}s`}
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
              <ReferenceLine
                y={average}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="4 4"
                strokeOpacity={0.4}
                label={{
                  value: `avg ${average}s`,
                  position: 'right',
                  fontSize: 10,
                  fill: 'hsl(var(--muted-foreground))',
                }}
              />
              <Area
                type="monotone"
                dataKey="totalDuration"
                stroke="#8b5cf6"
                strokeWidth={2}
                fill="url(#durationGradient)"
                dot={false}
                activeDot={{
                  r: 5,
                  fill: '#8b5cf6',
                  stroke: 'hsl(var(--background))',
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No processing time data available.</p>
            <p className="text-xs opacity-60">Run jobs to see the processing time trend.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default DurationTrendChart
