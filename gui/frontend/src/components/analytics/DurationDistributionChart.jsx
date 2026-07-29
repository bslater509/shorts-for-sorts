import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

const BUCKETS = [
  { key: '<30s', min: 0, max: 30 },
  { key: '30-60s', min: 30, max: 60 },
  { key: '60-90s', min: 60, max: 90 },
  { key: '90-120s', min: 90, max: 120 },
  { key: '120-180s', min: 120, max: 180 },
  { key: '180s+', min: 180, max: Infinity },
]

const BUCKET_COLORS = [
  '#c4b5fd',
  '#a78bfa',
  '#8b5cf6',
  '#7c3aed',
  '#6d28d9',
  '#4c1d95',
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const pct = entry.payload.pct
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1">{label}</p>
      <p className="text-xs text-muted-foreground">
        <span className="text-violet-400 font-semibold">{entry.value}</span> job{entry.value !== 1 ? 's' : ''}
      </p>
      <p className="text-xs text-muted-foreground">
        {pct}% of total
      </p>
    </div>
  )
}

const DurationDistributionChart = ({ perJobStats }) => {
  const distributionData = useMemo(() => {
    const total = perJobStats.length
    if (total === 0) return []

    const counts = BUCKETS.map(() => 0)
    perJobStats.forEach(job => {
      const duration = job.video_duration || 0
      for (let i = 0; i < BUCKETS.length; i++) {
        if (duration >= BUCKETS[i].min && duration < BUCKETS[i].max) {
          counts[i]++
          break
        }
      }
    })

    return BUCKETS.map((bucket, idx) => ({
      range: bucket.key,
      count: counts[idx],
      pct: total > 0 ? ((counts[idx] / total) * 100).toFixed(0) : 0,
      total,
    }))
  }, [perJobStats])

  const hasData = distributionData.some(d => d.count > 0)

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Video Duration Distribution</h2>
      <p className="text-xs text-muted-foreground mb-4">
        How your video lengths are spread across duration buckets
      </p>
      {hasData ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={distributionData}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              barCategoryGap={8}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                vertical={false}
              />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{
                  fill: 'hsl(var(--secondary))',
                  opacity: 0.15,
                }}
              />
              <Bar
                dataKey="count"
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              >
                {distributionData.map((entry, idx) => (
                  <Cell
                    key={entry.range}
                    fill={BUCKET_COLORS[idx % BUCKET_COLORS.length]}
                    style={{
                      filter: entry.count > 0
                        ? 'drop-shadow(0 2px 4px rgba(139, 92, 246, 0.2))'
                        : 'none',
                      transition: 'all 0.2s ease-out',
                    }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No video duration data available.</p>
            <p className="text-xs opacity-60">Run jobs with video output to see the distribution.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default DurationDistributionChart
