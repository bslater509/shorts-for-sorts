import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'

const PHASE_CONFIG = {
  llm: { label: 'LLM', fill: '#3b82f6', hoverFill: '#60a5fa' },
  voice: { label: 'Voice', fill: '#a855f7', hoverFill: '#c084fc' },
  transcribe: { label: 'Transcribe', fill: '#f59e0b', hoverFill: '#fbbf24' },
  render: { label: 'Render', fill: '#10b981', hoverFill: '#34d399' },
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null

  const total = payload.reduce((sum, entry) => sum + entry.value, 0)

  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3.5 py-2.5 shadow-xl text-sm min-w-[140px]">
      <p className="font-semibold text-foreground mb-2 text-xs uppercase tracking-wide">
        Job #{label}
      </p>
      <div className="space-y-1.5">
        {payload.map((entry) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-sm"
                style={{ backgroundColor: entry.fill }}
              />
              <span className="text-xs text-muted-foreground">{entry.name}</span>
            </div>
            <span className="text-xs font-medium text-foreground">{entry.value}s</span>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-2 border-t border-border/40 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Total</span>
        <span className="text-xs font-bold text-foreground">{total.toFixed(1)}s</span>
      </div>
    </div>
  )
}

const PerJobBreakdownChart = ({ stackedBarData }) => {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Per-Job Duration Breakdown</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Stacked view of LLM, Voice, Transcribe, and Render phases for each job
      </p>
      {stackedBarData.length > 0 ? (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={stackedBarData}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              barGap={2}
              barCategoryGap={8}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                vertical={false}
              />
              <XAxis
                dataKey="index"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Job #',
                  position: 'insideBottomRight',
                  offset: -5,
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
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
                verticalAlign="top"
                iconType="rect"
                formatter={(value) => (
                  <span className="text-sm text-muted-foreground">{value}</span>
                )}
                wrapperStyle={{ paddingBottom: 8 }}
              />
              {Object.entries(PHASE_CONFIG).map(([key, config]) => (
                <Bar
                  key={key}
                  dataKey={key}
                  stackId="a"
                  fill={config.fill}
                  name={config.label}
                  radius={[2, 2, 0, 0]}
                  maxBarSize={32}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-72 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No job duration data available.</p>
            <p className="text-xs opacity-60">Run a batch to see per-job breakdowns.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default PerJobBreakdownChart
