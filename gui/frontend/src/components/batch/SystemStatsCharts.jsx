import { useState } from 'react'
import {
  Cpu,
  MemoryStick,
  HardDrive,
  Activity,
  Network,
  Gauge,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'

const CARDS = [
  {
    key: 'cpu',
    label: 'CPU',
    icon: Cpu,
    color: '#3b82f6',
    chartKey: 'cpu',
    domain: [0, 100],
    value: (d) => `${Math.round(d.cpu)}%`,
  },
  {
    key: 'ram',
    label: 'RAM',
    icon: MemoryStick,
    color: '#a855f7',
    chartKey: 'ram',
    domain: [0, 100],
    value: (d) => `${Math.round(d.ram)}%`,
  },
  {
    key: 'disk',
    label: 'Disk',
    icon: HardDrive,
    color: '#f59e0b',
    chartKey: 'disk',
    domain: [0, 100],
    value: (d) => `${Math.round(d.disk)}%`,
  },
  {
    key: 'rss',
    label: 'Process RSS',
    icon: Activity,
    color: '#10b981',
    chartKey: 'rss',
    domain: ['auto', 'auto'],
    value: (d) => `${Math.round(d.rss)} MB`,
  },
  {
    key: 'net',
    label: 'Network',
    icon: Network,
    color: '#06b6d4',
    chartKey: 'netRecv',
    domain: ['auto', 'auto'],
    value: (d) => `↓ ${d.netRecv.toFixed(1)} KB/s`,
    extra: (d) => `↑ ${d.netSent.toFixed(1)} KB/s`,
  },
  {
    key: 'swap',
    label: 'Swap',
    icon: Gauge,
    color: '#f97316',
    chartKey: 'swap',
    domain: [0, 100],
    value: (d) => `${Math.round(d.swap)}%`,
  },
  {
    key: 'load',
    label: 'Load',
    icon: TrendingUp,
    color: '#64748b',
    chartKey: 'load',
    domain: ['auto', 'auto'],
    value: (d) => d.load.toFixed(2),
  },
]

const MetricCard = ({ card, latest, data, index }) => {
  const { key, label, icon: Icon, color, chartKey, domain } = card
  const gradId = `metric-${key}`

  return (
    <div
      className="group bg-background border border-border rounded-lg p-2 flex flex-col gap-1.5 shadow-sm relative overflow-hidden backdrop-blur-md animate-in fade-in slide-in-from-bottom-1 duration-300 fill-mode-both"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      {/* Tinted backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: `linear-gradient(135deg, ${color}0f 0%, transparent 55%)` }}
      />

      {/* Hover glow in the card's accent color */}
      <div
        className="absolute -inset-px rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ boxShadow: `0 0 20px -6px ${color}66` }}
      />

      <div className="flex items-center justify-between gap-2 relative min-w-0">
        <span className="text-[11px] font-semibold text-foreground/80 flex items-center gap-1.5 min-w-0">
          <Icon size={12} style={{ color }} className="shrink-0" />
          <span className="truncate">{label}</span>
        </span>
        <div className="flex flex-col items-end gap-0.5 shrink-0 min-w-0">
          <span
            className="text-sm font-bold tabular-nums leading-none whitespace-nowrap"
            style={{ color }}
          >
            {latest ? card.value(latest) : '—'}
          </span>
          {card.extra && (
            <span className="text-[9px] font-medium text-muted-foreground tabular-nums leading-none whitespace-nowrap">
              {latest ? card.extra(latest) : ''}
            </span>
          )}
        </div>
      </div>

      <div className="h-12 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 3, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis domain={domain} hide />
            <Area
              type="monotone"
              dataKey={chartKey}
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#${gradId})`}
              fillOpacity={1}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

const SystemStatsCharts = ({ systemStats }) => {
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768)

  const stats = systemStats || []
  const latest = stats.length > 0 ? stats[stats.length - 1] : null
  const hasData = stats.length > 0

  const chip = (Icon, value, className) => (
    <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold tabular-nums ${className}`}>
      <Icon size={10} /> {value}
    </span>
  )

  return (
    <div className="flex flex-col border-b border-border bg-secondary/10 shrink-0">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between gap-2 p-2 cursor-pointer hover:bg-secondary/20 transition-colors w-full text-left"
      >
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          System Stats
          {hasData && (
            <span className="relative flex h-1.5 w-1.5" title="Live">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {chip(Cpu, `${latest ? Math.round(latest.cpu) : 0}%`, 'border-blue-500/30 bg-blue-500/10 text-blue-400')}
          {chip(MemoryStick, `${latest ? Math.round(latest.ram) : 0}%`, 'border-purple-500/30 bg-purple-500/10 text-purple-400')}
          {chip(HardDrive, `${latest ? Math.round(latest.disk) : 0}%`, 'hidden sm:flex border-amber-500/30 bg-amber-500/10 text-amber-400')}
        </div>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 px-2 pb-2">
          {CARDS.map((card, i) => (
            <MetricCard key={card.key} card={card} latest={latest} data={stats} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

export default SystemStatsCharts
