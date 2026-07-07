import { useState, useEffect, useCallback } from 'react'
import { Layers, Play, Square, Loader2, CheckCircle2, XCircle, Clock, Cpu, HardDrive, ChevronDown, Check } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Batch() {
  const [numShorts, setNumShorts] = useState(5)
  const [batchData, setBatchData] = useState(null) // { in_progress, num_shorts, jobs: [] }
  const [systemStats, setSystemStats] = useState([])
  const [isStarting, setIsStarting] = useState(false)
  
  const [availablePrompts, setAvailablePrompts] = useState({})
  const [selectedPrompts, setSelectedPrompts] = useState([])
  const [showPromptDropdown, setShowPromptDropdown] = useState(false)

  // Fetch prompts on mount
  useEffect(() => {
    const fetchPrompts = async () => {
      try {
        const data = await api.fetchPrompts()
        setAvailablePrompts(data || {})
        setSelectedPrompts(Object.keys(data || {}))
      } catch (err) {
        console.error("Failed to fetch prompts", err)
      }
    }
    fetchPrompts()
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getBatchStatus()
      setBatchData(data)
      setSystemStats(prev => {
        const newStats = [...prev, { time: Date.now(), cpu: data.cpu_percent || 0, ram: data.memory_percent || 0 }]
        if (newStats.length > 30) newStats.shift()
        return newStats
      })
    } catch (err) {
      console.debug("Failed to fetch batch status", err)
    }
  }, [])

  // Poll continuously: fast when batch is active, slow when idle to reduce unnecessary requests
  useEffect(() => {
    fetchStatus()
    const delay = batchData?.in_progress ? 1000 : 5000
    const interval = setInterval(fetchStatus, delay)
    return () => clearInterval(interval)
  }, [fetchStatus, batchData?.in_progress])

  const handleStart = async () => {
    if (numShorts < 1) return
    if (selectedPrompts.length === 0) return alert("Please select at least one prompt template.")
    setIsStarting(true)
    try {
      await api.startBatch(numShorts, selectedPrompts)

    } catch (err) {
      alert(`Failed to start batch: ${err.message}`)
    } finally {
      setIsStarting(false)
    }
  }

  const handleCancel = async () => {
    try {
      await api.cancelBatch()
      alert("Cancellation requested")
    } catch (err) {
      alert(`Cancel failed: ${err.message}`)
    }
  }

  // Derived stats
  const jobs = batchData?.jobs || []
  const inProgress = batchData?.in_progress || false
  const totalJobs = batchData?.num_shorts || 0
  
  let doneCount = 0
  let runningCount = 0
  let failedCount = 0
  let queuedCount = 0
  
  let totalEtaSeconds = 0
  let activeJobsWithEta = 0
  
  jobs.forEach(job => {
    if (job.status === 'Done') doneCount++
    else if (job.failed || job.status?.startsWith('Failed')) failedCount++
    else if (job.status === 'Queued') queuedCount++
    else {
      runningCount++
      if (job.eta_seconds > 0) {
        totalEtaSeconds += job.eta_seconds
        activeJobsWithEta++
      }
    }
  })

  let globalEtaStr = "--"
  if (inProgress && runningCount > 0) {
    const avgActiveEta = activeJobsWithEta > 0 ? totalEtaSeconds / activeJobsWithEta : 60
    const queuedEta = queuedCount * 60
    const totalSeconds = avgActiveEta + queuedEta
    
    const m = Math.floor(totalSeconds / 60)
    const s = Math.floor(totalSeconds % 60)
    globalEtaStr = m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)]">
      <header className="shrink-0 flex flex-col sm:flex-row items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Layers className="text-blue-500" />
            Batch Generator
          </h1>
          <p className="text-muted-foreground mt-1">Generate multiple videos autonomously using AI selected topics and configured layouts.</p>
        </div>
        
        <div className="flex items-center gap-3 bg-secondary/50 border border-border rounded-xl p-2 shrink-0 shadow-sm">
          <div className="flex items-center gap-2 px-2">
            <label className="text-sm font-medium">Quantity</label>
            <input 
              type="number" 
              min="1" 
              max="50"
              className="w-16 bg-background border border-border rounded-md px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              value={numShorts}
              onChange={(e) => setNumShorts(parseInt(e.target.value) || 1)}
              disabled={inProgress}
            />
          </div>
          
          <div className="relative">
            <button 
              onClick={() => setShowPromptDropdown(!showPromptDropdown)}
              disabled={inProgress}
              className="flex items-center gap-2 bg-background border border-border rounded-md px-3 py-1.5 text-sm font-medium hover:bg-secondary/50 transition-colors disabled:opacity-50"
            >
              Prompts ({selectedPrompts.length}) <ChevronDown size={14} />
            </button>
            {showPromptDropdown && !inProgress && (
              <div className="absolute top-full mt-2 right-0 md:right-auto md:left-0 w-72 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-80">
                <div className="p-2 border-b border-border bg-secondary/30 flex justify-between items-center text-xs">
                  <span className="font-semibold text-muted-foreground">Select Prompts</span>
                  <div className="space-x-2">
                    <button onClick={() => setSelectedPrompts(Object.keys(availablePrompts))} className="text-blue-500 hover:underline">All</button>
                    <button onClick={() => setSelectedPrompts([])} className="text-muted-foreground hover:underline">None</button>
                  </div>
                </div>
                <div className="overflow-y-auto p-1">
                  {Object.keys(availablePrompts).length === 0 && <div className="p-2 text-xs text-muted-foreground text-center">No prompts found</div>}
                  {Object.keys(availablePrompts).map(key => (
                    <label key={key} className="flex items-start gap-2 p-2 hover:bg-secondary/50 rounded cursor-pointer">
                      <div className="mt-0.5 flex-shrink-0 flex items-center justify-center w-4 h-4 rounded border border-border bg-background">
                        {selectedPrompts.includes(key) && <Check size={12} className="text-blue-500" />}
                      </div>
                      <input 
                        type="checkbox" 
                        className="hidden"
                        checked={selectedPrompts.includes(key)}
                        onChange={(e) => {
                          if (e.target.checked) setSelectedPrompts(prev => [...prev, key])
                          else setSelectedPrompts(prev => prev.filter(p => p !== key))
                        }}
                      />
                      <div className="flex flex-col">
                        <span className="text-sm font-medium leading-none">{key}</span>
                        <span className="text-xs text-muted-foreground mt-1 line-clamp-1" title={availablePrompts[key]}>{availablePrompts[key]}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button 
            onClick={handleStart}
            disabled={inProgress || isStarting || selectedPrompts.length === 0}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg font-medium text-sm transition-all bg-blue-500 hover:bg-blue-600 text-white shadow-md disabled:opacity-50"
          >
            {isStarting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Start Batch
          </button>
        </div>
      </header>

      <div className="flex-1 bg-card border border-border rounded-xl shadow-sm md:overflow-hidden flex flex-col">
        {/* Status Header */}
        <div className="bg-secondary/30 border-b border-border p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shrink-0">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 font-medium">
              <span className={cn("flex h-3 w-3 rounded-full", inProgress ? "bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]" : "bg-muted-foreground")} />
              {inProgress ? 'Batch Running...' : 'Idle'}
            </div>
            
            {batchData && (
              <div className="flex flex-wrap items-center gap-3 text-sm font-medium sm:border-l border-border sm:pl-4">
                <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 size={14}/> {doneCount} Done</span>
                <span className="text-blue-500 flex items-center gap-1"><Loader2 size={14} className={cn(runningCount > 0 && "animate-spin")}/> {runningCount} Running</span>
                <span className="text-red-500 flex items-center gap-1"><XCircle size={14}/> {failedCount} Failed</span>
                <span className="text-muted-foreground flex items-center gap-1"><Clock size={14}/> {queuedCount} Queued</span>
                <span className="text-foreground ml-2 border-r border-border pr-3">Total: {totalJobs}</span>
                {inProgress && (
                  <span className="text-purple-400 flex items-center gap-1 font-bold bg-purple-500/10 px-2 py-0.5 rounded-md border border-purple-500/20 shadow-[0_0_10px_rgba(168,85,247,0.2)] animate-in fade-in">
                    ETA: {globalEtaStr}
                  </span>
                )}
              </div>
            )}
          </div>
          
          {inProgress && (
            <button 
              onClick={handleCancel}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-xs transition-all bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20"
            >
              <Square size={14} />
              Cancel Batch
            </button>
          )}
        </div>

        {/* System Stats Charts */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 border-b border-border bg-secondary/10 shrink-0">
          <div className="bg-background border border-border rounded-xl p-4 flex flex-col gap-2 shadow-sm relative overflow-hidden backdrop-blur-md">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none" />
            <div className="flex items-center justify-between relative">
              <span className="text-sm font-semibold flex items-center gap-2"><Cpu size={16} className="text-blue-500" /> CPU Usage</span>
              <span className="text-xs font-medium text-muted-foreground">{systemStats.length > 0 ? systemStats[systemStats.length - 1].cpu : 0}%</span>
            </div>
            <div className="h-24 w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={systemStats}>
                  <defs>
                    <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <YAxis domain={[0, 100]} hide />
                  <Area type="monotone" dataKey="cpu" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorCpu)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-background border border-border rounded-xl p-4 flex flex-col gap-2 shadow-sm relative overflow-hidden backdrop-blur-md">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent pointer-events-none" />
            <div className="flex items-center justify-between relative">
              <span className="text-sm font-semibold flex items-center gap-2"><HardDrive size={16} className="text-purple-500" /> RAM Usage</span>
              <span className="text-xs font-medium text-muted-foreground">{systemStats.length > 0 ? systemStats[systemStats.length - 1].ram : 0}%</span>
            </div>
            <div className="h-24 w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={systemStats}>
                  <defs>
                    <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <YAxis domain={[0, 100]} hide />
                  <Area type="monotone" dataKey="ram" stroke="#a855f7" strokeWidth={2} fillOpacity={1} fill="url(#colorRam)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Jobs Grid */}
        <div className="flex-1 md:overflow-y-auto p-6 bg-secondary/10">
          {jobs.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...jobs].sort((a, b) => {
                if (a.status === 'Done' && b.status !== 'Done') return 1;
                if (b.status === 'Done' && a.status !== 'Done') return -1;
                return (b.progress || 0) - (a.progress || 0);
              }).map((job) => {
                const isDone = job.status === 'Done'
                const isFailed = job.failed || job.status?.startsWith('Failed')
                const isQueued = job.status === 'Queued'
                const isRunning = !isDone && !isFailed && !isQueued
                const p = job.progress || 0

                return (
                  <div key={job.id} className="bg-background border border-border/50 rounded-xl p-4 flex flex-col gap-3 shadow-sm hover:border-blue-500/30 hover:shadow-[0_4px_20px_-4px_rgba(59,130,246,0.1)] transition-all duration-300 relative overflow-hidden backdrop-blur-sm">
                    {isRunning && <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 via-transparent to-transparent pointer-events-none" />}
                    <div className="flex justify-between items-start relative">
                      <div />
                      <div className="flex gap-2">
                        {job.eta && job.eta !== '--' && job.eta !== '0s' && (
                          <span className="text-xs font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-md border border-purple-500/20 shadow-[0_0_8px_rgba(168,85,247,0.15)]">
                            ETA: {job.eta}
                          </span>
                        )}
                        <span className="text-xs font-medium text-muted-foreground bg-secondary/80 px-2 py-0.5 rounded-md border border-border/50">
                          {job.elapsed}
                        </span>
                      </div>
                    </div>
                    
                    <div className="space-y-1 relative">
                      <h4 className="font-semibold text-sm leading-tight line-clamp-2" title={job.topic}>
                        {job.topic || "Generating topic..."}
                      </h4>
                      <p className="text-xs text-muted-foreground">
                        {job.voice || "Auto Voice"} • {job.layout || "Auto Layout"}
                      </p>
                    </div>

                    <div className="mt-auto pt-3 border-t border-border/50 relative">
                      {isDone && <span className="text-emerald-500 text-sm font-semibold flex items-center gap-1 drop-shadow-[0_0_4px_rgba(16,185,129,0.5)]"><CheckCircle2 size={16}/> Completed</span>}
                      {isFailed && <span className="text-red-500 text-sm font-semibold flex items-center gap-1 drop-shadow-[0_0_4px_rgba(239,68,68,0.5)]"><XCircle size={16}/> {job.status}</span>}
                      {isQueued && <span className="text-muted-foreground text-sm font-medium flex items-center gap-1"><Clock size={16}/> Queued...</span>}
                      
                      {isRunning && (
                        <div className="space-y-2">
                          <div className="flex justify-between text-xs font-medium">
                            <span className="text-blue-500 truncate pr-2 drop-shadow-[0_0_2px_rgba(59,130,246,0.3)]">{job.status}</span>
                            <span className="text-foreground shrink-0">{p}%</span>
                          </div>
                          <MultiSegmentProgressBar progress={p} />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground space-y-3">
              <Layers size={48} className="opacity-20" />
              <p>No batch jobs running or completed in this session.</p>
              <p className="text-sm">Set a quantity and click Start Batch to generate videos automatically.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const MultiSegmentProgressBar = ({ progress }) => {
  // progress is 0-100
  const p1 = Math.min(100, Math.max(0, (progress / 20) * 100))
  const p2 = Math.min(100, Math.max(0, ((progress - 20) / 25) * 100))
  const p3 = Math.min(100, Math.max(0, ((progress - 45) / 10) * 100))
  const p4 = Math.min(100, Math.max(0, ((progress - 55) / 45) * 100))

  return (
    <div className="w-full flex gap-1 h-2 rounded-full overflow-hidden bg-background/50 border border-border/50">
      <div className="h-full bg-secondary/40" style={{ flex: 20 }}>
        <div className="h-full bg-gradient-to-r from-pink-500 to-rose-500 transition-all duration-300 ease-out shadow-[0_0_8px_rgba(236,72,153,0.6)]" style={{ width: `${p1}%` }} />
      </div>
      <div className="h-full bg-secondary/40" style={{ flex: 25 }}>
        <div className="h-full bg-gradient-to-r from-rose-500 to-amber-500 transition-all duration-300 ease-out shadow-[0_0_8px_rgba(245,158,11,0.6)]" style={{ width: `${p2}%` }} />
      </div>
      <div className="h-full bg-secondary/40" style={{ flex: 10 }}>
        <div className="h-full bg-gradient-to-r from-amber-500 to-emerald-500 transition-all duration-300 ease-out shadow-[0_0_8px_rgba(16,185,129,0.6)]" style={{ width: `${p3}%` }} />
      </div>
      <div className="h-full bg-secondary/40" style={{ flex: 45 }}>
        <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-300 ease-out shadow-[0_0_8px_rgba(6,182,212,0.6)]" style={{ width: `${p4}%` }} />
      </div>
    </div>
  )
}
