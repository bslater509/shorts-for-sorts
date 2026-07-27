import { useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

// Generates a gradient of purple shades based on index
const BAR_COLORS = [
  { fill: '#7c3aed', hover: '#8b5cf6' },
  { fill: '#6d28d9', hover: '#7c3aed' },
  { fill: '#5b21b6', hover: '#6d28d9' },
  { fill: '#4c1d95', hover: '#5b21b6' },
  { fill: '#3b0764', hover: '#4c1d95' },
]

const CustomBar = ({ x, y, width, height, fill, payload, isHovered, onMouseEnter, onMouseLeave }) => {
  const radius = 4
  const hoverScale = isHovered ? 1.08 : 1

  return (
    <g
      onMouseEnter={() => onMouseEnter(payload)}
      onMouseLeave={onMouseLeave}
      style={{ cursor: 'pointer' }}
    >
      <rect
        x={x}
        y={y - (height * (hoverScale - 1)) / 2}
        width={width * hoverScale}
        height={height * hoverScale}
        fill={fill}
        rx={radius}
        ry={radius}
        style={{
          filter: isHovered ? 'drop-shadow(0 0 6px rgba(139, 92, 246, 0.35))' : 'none',
          transition: 'all 0.25s ease-out',
        }}
      />
      {/* Glow overlay on hover */}
      {isHovered && (
        <rect
          x={x + width * 0.02}
          y={y - (height * (hoverScale - 1)) / 2 + 2}
          width={width * 0.2}
          height={height * hoverScale - 4}
          fill="white"
          opacity={0.08}
          rx={radius}
          ry={radius}
        />
      )}
    </g>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2.5 shadow-xl text-sm">
      <p className="font-medium text-foreground mb-1">{label}</p>
      <p className="text-xs text-muted-foreground">
        Avg duration:{' '}
        <span className="text-purple-400 font-semibold">{entry.value}s</span>
      </p>
    </div>
  )
}

const DurationByVoiceChart = ({ voiceDurationData }) => {
  const [hoveredVoice, setHoveredVoice] = useState(null)

  const handleMouseEnter = useCallback((payload) => {
    setHoveredVoice(payload.voice)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setHoveredVoice(null)
  }, [])

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Avg Duration by Voice</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Average total processing time grouped by voice ID
      </p>
      {voiceDurationData.length > 0 ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={voiceDurationData}
              layout="vertical"
              margin={{ top: 5, right: 24, left: 10, bottom: 5 }}
              barCategoryGap={12}
            >
              <defs>
                <linearGradient id="voiceBarGradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.6} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
                horizontal={false}
              />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={v => `${v}s`}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="voice"
                width={100}
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={false}
              />
              <Bar
                dataKey="avgDuration"
                radius={[0, 4, 4, 0]}
                shape={(props) => (
                  <CustomBar
                    {...props}
                    isHovered={hoveredVoice === props.payload.voice}
                    onMouseEnter={handleMouseEnter}
                    onMouseLeave={handleMouseLeave}
                  />
                )}
              >
                {voiceDurationData.map((entry, idx) => (
                  <Cell
                    key={entry.voice}
                    fill={BAR_COLORS[idx % BAR_COLORS.length].fill}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>No voice data available.</p>
            <p className="text-xs opacity-60">Voice-specific durations appear once jobs are processed.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default DurationByVoiceChart
