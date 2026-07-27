import { useState, useCallback } from 'react'
import { PieChart, Pie, Cell, Sector, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const COLORS = [
  { base: '#3b82f6', light: '#60a5fa', dark: '#2563eb' },
  { base: '#a855f7', light: '#c084fc', dark: '#7c3aed' },
  { base: '#f59e0b', light: '#fbbf24', dark: '#d97706' },
  { base: '#10b981', light: '#34d399', dark: '#059669' },
]

const renderActiveShape = (props) => {
  const {
    cx, cy, innerRadius, outerRadius, startAngle, endAngle,
    fill,
  } = props
  return (
    <g>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        stroke="hsl(var(--background))"
        strokeWidth={3}
        style={{ filter: 'drop-shadow(0 0 8px rgba(168, 85, 247, 0.3))' }}
      />
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius + 2}
        outerRadius={outerRadius - 4}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.15}
      />
    </g>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3 py-2 shadow-xl text-sm">
      <div className="flex items-center gap-2 mb-1">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: entry.payload.fill }}
        />
        <span className="font-medium text-foreground">{entry.name}</span>
      </div>
      <p className="text-muted-foreground text-xs">
        <span className="text-foreground font-semibold">{entry.value}%</span> of total
      </p>
    </div>
  )
}

const PhaseDistributionChart = ({ phaseData }) => {
  const [activeIndex, setActiveIndex] = useState(null)

  const onPieEnter = useCallback((_, index) => setActiveIndex(index), [])
  const onPieLeave = useCallback(() => setActiveIndex(null), [])

  const totalValue = phaseData.reduce((sum, d) => sum + d.value, 0)

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Phase Distribution</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Proportion of time spent in each processing phase
      </p>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <defs>
              {COLORS.map((c, i) => (
                <linearGradient key={i} id={`phaseGradient${i}`} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor={c.light} />
                  <stop offset="100%" stopColor={c.dark} />
                </linearGradient>
              ))}
            </defs>
            <Pie
              data={phaseData}
              cx="50%"
              cy="50%"
              innerRadius={68}
              outerRadius={108}
              paddingAngle={3}
              dataKey="value"
              activeIndex={activeIndex != null ? activeIndex : undefined}
              activeShape={renderActiveShape}
              onMouseEnter={onPieEnter}
              onMouseLeave={onPieLeave}
              stroke="transparent"
            >
              {phaseData.map((entry, idx) => (
                <Cell
                  key={entry.name}
                  fill={`url(#phaseGradient${idx})`}
                />
              ))}
            </Pie>

            {/* Center label */}
            {activeIndex == null ? (
              <>
                <text
                  x="50%"
                  y="46%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-foreground text-2xl font-bold"
                >
                  {totalValue}%
                </text>
                <text
                  x="50%"
                  y="56%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-muted-foreground text-[10px] uppercase tracking-[0.15em]"
                >
                  Total
                </text>
              </>
            ) : (
              <>
                <text
                  x="50%"
                  y="46%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-foreground text-2xl font-bold"
                >
                  {phaseData[activeIndex]?.value}%
                </text>
                <text
                  x="50%"
                  y="56%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-muted-foreground text-[10px] uppercase tracking-[0.15em]"
                >
                  {phaseData[activeIndex]?.name}
                </text>
              </>
            )}

            <Tooltip
              content={<CustomTooltip />}
              cursor={false}
            />
            <Legend
              verticalAlign="bottom"
              iconType="circle"
              formatter={(value) => {
                const entry = phaseData.find(d => d.name === value)
                return (
                  <span className="text-sm text-muted-foreground transition-colors duration-200">
                    {value}{' '}
                    <span className="text-foreground/60 font-medium">
                      {entry ? `${entry.value}%` : ''}
                    </span>
                  </span>
                )
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default PhaseDistributionChart
