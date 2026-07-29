import { Cpu, HardDrive } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'

const SystemStatsCharts = ({ systemStats }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2 border-b border-border bg-secondary/10 shrink-0">
      <div className="bg-background border border-border rounded-lg p-2 flex flex-col gap-1 shadow-sm relative overflow-hidden backdrop-blur-md">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none" />
        <div className="flex items-center justify-between relative">
          <span className="text-xs font-semibold flex items-center gap-1.5"><Cpu size={12} className="text-blue-500" /> CPU</span>
          <span className="text-[10px] font-medium text-muted-foreground">{systemStats.length > 0 ? systemStats[systemStats.length - 1].cpu : 0}%</span>
        </div>
        <div className="h-12 w-full relative">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={systemStats}>
              <defs>
                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <YAxis domain={[0, 100]} hide />
              <Area type="monotone" dataKey="cpu" stroke="#3b82f6" strokeWidth={1.5} fillOpacity={1} fill="url(#colorCpu)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="bg-background border border-border rounded-lg p-2 flex flex-col gap-1 shadow-sm relative overflow-hidden backdrop-blur-md">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent pointer-events-none" />
        <div className="flex items-center justify-between relative">
          <span className="text-xs font-semibold flex items-center gap-1.5"><HardDrive size={12} className="text-purple-500" /> RAM</span>
          <span className="text-[10px] font-medium text-muted-foreground">{systemStats.length > 0 ? systemStats[systemStats.length - 1].ram : 0}%</span>
        </div>
        <div className="h-12 w-full relative">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={systemStats}>
              <defs>
                <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <YAxis domain={[0, 100]} hide />
              <Area type="monotone" dataKey="ram" stroke="#a855f7" strokeWidth={1.5} fillOpacity={1} fill="url(#colorRam)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default SystemStatsCharts
