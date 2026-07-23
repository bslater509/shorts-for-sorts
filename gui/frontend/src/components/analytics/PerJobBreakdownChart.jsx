import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const PerJobBreakdownChart = ({ stackedBarData }) => {
  return (
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
  )
}

export default PerJobBreakdownChart
