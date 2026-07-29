import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

const BUCKETS = [
  { key: '1-5', min: 1, max: 6 },
  { key: '6-10', min: 6, max: 11 },
  { key: '11-15', min: 11, max: 16 },
  { key: '16-20', min: 16, max: 21 },
  { key: '21-30', min: 21, max: 31 },
  { key: '30+', min: 31, max: Infinity },
]

const BUCKET_COLORS = [
  '#a5b4fc',
  '#818cf8',
  '#6366f1',
  '#4f46e5',
  '#4338ca',
  '#3730a3',
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const pct = entry.payload.pct
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1">{label}</p>
      <p className="text-xs text-muted-foreground">
        <span className="text-indigo-400 font-semibold">{entry.value}</span> job{entry.value !== 1 ? 's' : ''}
      </p>
      <p className="text-xs text-muted-foreground">
        {pct}% of total
      </p>
    </div>
  )
}

const ChunkDistributionChart = ({ perJobStats = [] }) => {
  const distributionData = useMemo(() => {
    const total = perJobStats.length
    if (total === 0) return []

    const counts = BUCKETS.map(() => 0)
    perJobStats.forEach(job => {
      const chunks = job.chunk_count || 0
      for (let i = 0; i < BUCKETS.length; i++) {
        if (chunks >= BUCKETS[i].min && chunks < BUCKETS[i].max) {
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
      <h2 className="text-lg font-semibold mb-2">Chunk Count Distribution</h2>
      <p className="text-xs text-muted-foreground mb-4">
        How many text chunks (TTS segments) your scripts are split into
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
                        ? 'drop-shadow(0 2px 4px rgba(99, 102, 241, 0.2))'
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
            <p>No chunk data available.</p>
            <p className="text-xs opacity-60">Run jobs with chunked content to see the distribution.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChunkDistributionChart
