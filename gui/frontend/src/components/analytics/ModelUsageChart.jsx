import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList,
} from 'recharts'

const MODEL_COLORS = [
  '#c7d2fe',
  '#a5b4fc',
  '#818cf8',
  '#6366f1',
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

const ModelUsageChart = ({ perJobStats = [] }) => {
  const usageData = useMemo(() => {
    const counts = {}
    perJobStats.forEach(job => {
      const model = job.model || 'Unknown'
      counts[model] = (counts[model] || 0) + 1
    })

    const total = perJobStats.length

    if (total > 0 && Object.keys(counts).length === 1 && counts['Unknown'] === total) {
      return [] // all empty — signal no data
    }

    // Remove 'Unknown' key if counts reflect truly empty models
    const hasRealModel = Object.keys(counts).some(k => k !== 'Unknown')
    if (!hasRealModel) return []

    const sorted = Object.entries(counts)
      .filter(([model]) => model !== 'Unknown' || counts['Unknown'] < total)
      .map(([model, count]) => ({
        model,
        count,
        pct: total > 0 ? ((count / total) * 100).toFixed(0) : 0,
      }))
      .sort((a, b) => b.count - a.count)

    return sorted
  }, [perJobStats])

  const hasData = usageData.length > 0

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">LLM Model Usage</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Which AI models are used across batch jobs
      </p>
      {hasData ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={usageData}
              layout="vertical"
              margin={{ top: 5, right: 50, left: 10, bottom: 5 }}
              barCategoryGap={8}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                horizontal={false}
              />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="model"
                width={110}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={false}
              />
              <Bar
                dataKey="count"
                radius={[0, 4, 4, 0]}
                maxBarSize={28}
              >
                <LabelList
                  dataKey="count"
                  position="right"
                  style={{
                    fontSize: 11,
                    fill: 'hsl(var(--foreground))',
                    fontWeight: 500,
                  }}
                />
                {usageData.map((entry, idx) => (
                  <Cell
                    key={entry.model}
                    fill={MODEL_COLORS[idx % MODEL_COLORS.length]}
                    style={{
                      filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.15))',
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
            <p>Model data available after next batch.</p>
            <p className="text-xs opacity-60">Run a batch to see which models are being used.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ModelUsageChart
