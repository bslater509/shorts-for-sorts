import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1.5">{label}</p>
      <div className="space-y-1">
        {payload.map((entry, idx) => (
          <div key={idx} className="flex justify-between gap-4">
            <span className="text-xs text-muted-foreground">{entry.name}</span>
            <span className="text-xs font-medium text-foreground">{entry.value.toFixed(1)}s</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const LayoutComparisonChart = ({ perJobStats = [] }) => {
  const comparisonData = useMemo(() => {
    const groups = {}

    perJobStats.forEach(job => {
      const layout = job.layout || 'Unknown'
      if (!groups[layout]) {
        groups[layout] = { jobs: [], processingTotal: 0, durationTotal: 0, count: 0 }
      }
      const processing = (job.llm_duration || 0) + (job.voice_duration || 0) + (job.transcribe_duration || 0) + (job.render_duration || 0)
      groups[layout].processingTotal += processing
      groups[layout].durationTotal += (job.video_duration || 0)
      groups[layout].count++
    })

    return Object.entries(groups)
      .map(([layout, data]) => ({
        layout,
        avgProcessing: data.count > 0 ? parseFloat((data.processingTotal / data.count).toFixed(1)) : 0,
        avgDuration: data.count > 0 ? parseFloat((data.durationTotal / data.count).toFixed(1)) : 0,
      }))
      .sort((a, b) => b.avgProcessing - a.avgProcessing)
  }, [perJobStats])

  const hasData = comparisonData.length > 0

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Layout Performance Comparison</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Average processing time and video duration for Split-Screen vs Full Screen layouts
      </p>
      {hasData ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={comparisonData}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              barCategoryGap={16}
              barGap={4}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                vertical={false}
              />
              <XAxis
                dataKey="layout"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
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
                  fill: 'hsl(var(--secondary))',
                  opacity: 0.15,
                }}
              />
              <Legend
                wrapperStyle={{
                  fontSize: 11,
                  color: 'hsl(var(--muted-foreground))',
                }}
                iconType="rect"
                iconSize={10}
              />
              <Bar
                dataKey="avgProcessing"
                name="Avg Processing"
                fill="#8b5cf6"
                radius={[4, 4, 0, 0]}
                barSize={32}
                style={{
                  filter: 'drop-shadow(0 2px 4px rgba(139, 92, 246, 0.2))',
                  transition: 'all 0.2s ease-out',
                }}
              />
              <Bar
                dataKey="avgDuration"
                name="Avg Duration"
                fill="#10b981"
                radius={[4, 4, 0, 0]}
                barSize={32}
                style={{
                  filter: 'drop-shadow(0 2px 4px rgba(16, 185, 129, 0.2))',
                  transition: 'all 0.2s ease-out',
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No layout data available for comparison.</p>
            <p className="text-xs opacity-60">Run jobs with different layouts to see the comparison.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default LayoutComparisonChart
