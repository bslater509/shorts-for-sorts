import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList,
} from 'recharts'

const VOICE_COLORS = [
  '#8b5cf6', '#06b6d4', '#f59e0b', '#10b981',
  '#ef4444', '#ec4899', '#f97316', '#14b8a6',
  '#6366f1', '#d946ef',
]

const VOICE_NAMES = {
  '21m00Tcm4TlvDq8ikWAM': 'Rachel',
  'AZnzlk1XvdvUeBnXmlld': 'Domi',
  'EXAVITQu4vrCxn2k5eS': 'Bella',
  'ErXwobaYiN019PkySvj': 'Antoni',
  'MF3mGyEYCl7XYWbV9V6w': 'Elli',
  'TxGEqnHWrfWFTfGW9Xj': 'Josh',
  'VR6AewLTigWG4xSOGB': 'Arnold',
  'W7Kpb6O9M2Zq3Gx7Pz': 'Emily',
  'XU6kD4G6lVX7zQg9sF': 'Liam',
  'ZQe5CZ4zR8r0Gk6yLm': 'Olivia',
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const pct = entry.payload.pct
  const displayName = VOICE_NAMES[entry.payload.voice] || entry.payload.voice
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1">{displayName}</p>
      <p className="text-xs text-muted-foreground">
        <span className="text-purple-400 font-semibold">{entry.value}</span> job{entry.value !== 1 ? 's' : ''}
      </p>
      <p className="text-xs text-muted-foreground">
        {pct}% of total
      </p>
    </div>
  )
}

const VoiceUsageChart = ({ perJobStats = [] }) => {
  const usageData = useMemo(() => {
    const counts = {}
    perJobStats.forEach(job => {
      const voice = job.voice_id || 'Unknown'
      counts[voice] = (counts[voice] || 0) + 1
    })

    const total = perJobStats.length
    const sorted = Object.entries(counts)
      .map(([voice, count]) => ({
        voice,
        count,
        pct: total > 0 ? ((count / total) * 100).toFixed(0) : 0,
      }))
      .sort((a, b) => b.count - a.count)

    return sorted
  }, [perJobStats])

  const hasData = usageData.length > 0

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Voice Usage Frequency</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Which voices are used most across batch jobs
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
                dataKey="voice"
                width={90}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={(val) => VOICE_NAMES[val] || val}
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
                    key={entry.voice}
                    fill={VOICE_COLORS[idx % VOICE_COLORS.length]}
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
            <p>No voice usage data available.</p>
            <p className="text-xs opacity-60">Voice data will appear once jobs are processed.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default VoiceUsageChart
