import { useState, useCallback, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'

const BAR_COLORS = [
  { fill: '#8b5cf6', hover: '#a78bfa' },
  { fill: '#06b6d4', hover: '#22d3ee' },
  { fill: '#f59e0b', hover: '#fbbf24' },
  { fill: '#10b981', hover: '#34d399' },
  { fill: '#ef4444', hover: '#f87171' },
  { fill: '#ec4899', hover: '#f472b6' },
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
        Speaking speed:{' '}
        <span className="text-violet-400 font-semibold">{entry.value} w/s</span>
      </p>
    </div>
  )
}

const SpeakingSpeedByVoiceChart = ({ perJobStats }) => {
  const [hoveredVoice, setHoveredVoice] = useState(null)

  const handleMouseEnter = useCallback((payload) => {
    setHoveredVoice(payload.voice)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setHoveredVoice(null)
  }, [])

  // Group by voice and compute avg words per second of voice output
  const voiceSpeedData = useMemo(() => {
    const voiceMap = {}
    perJobStats.forEach(job => {
      const voice = job.voice_id || 'Unknown'
      if (!voiceMap[voice]) voiceMap[voice] = { totalWords: 0, totalVoiceDuration: 0 }
      voiceMap[voice].totalWords += job.word_count || 0
      voiceMap[voice].totalVoiceDuration += job.voice_duration || 0
    })
    return Object.entries(voiceMap)
      .map(([voice, { totalWords, totalVoiceDuration }]) => ({
        voice: voice.length > 20 ? voice.slice(0, 20) + '…' : voice,
        fullVoice: voice,
        wps: totalVoiceDuration > 0 ? parseFloat((totalWords / totalVoiceDuration).toFixed(1)) : 0,
      }))
      .sort((a, b) => b.wps - a.wps)
  }, [perJobStats])

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Speaking Speed by Voice</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Average words per second of voice output, grouped by voice ID
      </p>
      {voiceSpeedData.length > 0 ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={voiceSpeedData}
              layout="vertical"
              margin={{ top: 5, right: 24, left: 10, bottom: 5 }}
              barCategoryGap={12}
            >
              <defs>
                <linearGradient id="speechBarGradient" x1="0" y1="0" x2="1" y2="0">
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
                tickFormatter={v => `${v} w/s`}
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
                dataKey="wps"
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
                {voiceSpeedData.map((entry, idx) => (
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
            <p>No voice speed data available.</p>
            <p className="text-xs opacity-60">Speaking rate data appears once jobs are processed.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default SpeakingSpeedByVoiceChart
