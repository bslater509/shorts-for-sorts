import { useState, useEffect, useCallback } from 'react'
import { Layers, Play, Square, Loader2, CheckCircle2, XCircle, Clock, Cpu, HardDrive, ChevronDown, Check, RefreshCw, Download, X, Activity, Sparkles, Type, Smile, Volume2, Film, FileText, MessageSquare, Terminal } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'

export default function Batch() {
  const defaultBatchSize = useAppStore((s) => s.settings?.default_batch_size) || 1
  const numShorts = useAppStore((s) => s.appState?.batch_num_shorts || defaultBatchSize)
  const emojiScaleFactor = useAppStore((s) => s.appState?.emoji_scale_factor || 1.5)
  const emojiHoldDuration = useAppStore((s) => s.appState?.emoji_hold_duration || 0.5)
  const emojiThrowMaxCount = useAppStore((s) => s.appState?.emoji_throw_max_count || 3)
  const updateAppState = useAppStore((s) => s.updateAppState)
  const saveCurrentState = useAppStore((s) => s.saveCurrentState)
  const [batchData, setBatchData] = useState(null) // { in_progress, num_shorts, jobs: [] }
  const [systemStats, setSystemStats] = useState([])
  const [isStarting, setIsStarting] = useState(false)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [jobDetail, setJobDetail] = useState(null)
  
  const [availablePrompts, setAvailablePrompts] = useState({})
  const [selectedPrompts, setSelectedPrompts] = useState([])
  const [showPromptDropdown, setShowPromptDropdown] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [connectionError, setConnectionError] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [enableEmojis, setEnableEmojis] = useState(true)
  const [enableEmojiAnimation, setEnableEmojiAnimation] = useState(true)
  const [emojiStyles, setEmojiStyles] = useState(['apple', 'twemoji'])

  const AVAILABLE_EMOJI_STYLES = [
    { id: 'apple', label: 'Apple' },
    { id: 'twemoji', label: 'Twemoji' },
    { id: 'google', label: 'Google' },
    { id: 'facebook', label: 'Facebook' },
    { id: 'openmoji', label: 'OpenMoji' }
  ]

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
      setConnectionError(false)
      setInitialLoading(false)
      setBatchData(data)
      setSystemStats(prev => {
        const newStats = [...prev, { time: Date.now(), cpu: data.cpu_percent || 0, ram: data.memory_percent || 0 }]
        if (newStats.length > 30) newStats.shift()
        return newStats
      })
    } catch (err) {
      console.debug("Failed to fetch batch status", err)
      setConnectionError(true)
      setInitialLoading(false)
    }
  }, [])

  // Poll continuously: fast when batch is active, slow when idle to reduce unnecessary requests
  useEffect(() => {
    fetchStatus()
    const delay = batchData?.in_progress ? 1000 : 5000
    const interval = setInterval(fetchStatus, delay)
    return () => clearInterval(interval)
  }, [fetchStatus, batchData?.in_progress])

  // Poll selected job detail
  useEffect(() => {
    if (!selectedJobId) { setJobDetail(null); return }
    const fetchDetail = async () => {
      try {
        const data = await api.getJobDetail(selectedJobId)
        setJobDetail(data)
      } catch (err) {
        console.debug("Failed to fetch job detail", err)
      }
    }
    fetchDetail()
    // Don't poll if the job is already completed
    const jobFromBatch = batchData?.jobs?.find(j => j.id === selectedJobId)
    if (jobFromBatch?.status === 'Done') return
    const delay = batchData?.in_progress ? 1000 : 5000
    const interval = setInterval(fetchDetail, delay)
    return () => clearInterval(interval)
  }, [selectedJobId, batchData?.in_progress, batchData?.jobs])

  const handleStart = async () => {
    if (numShorts < 1) return
    if (selectedPrompts.length === 0) return alert("Please select at least one prompt template.")
    setIsStarting(true)
    try {
      await api.startBatch(numShorts, selectedPrompts, enableEmojis,
          enableEmojiAnimation, emojiScaleFactor, emojiHoldDuration,
          emojiThrowMaxCount, emojiStyles)
      fetchStatus()
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

  const handleRetryFailed = async () => {
    setIsRetrying(true)
    try {
      await api.retryFailedBatch()
      setIsRetrying(false)
    } catch (err) {
      alert(`Retry failed: ${err.message}`)
      setIsRetrying(false)
    }
  }

  const handleDownloadReport = async () => {
    try {
      const report = await api.getBatchReport()
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `batch-report-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(`Failed to download report: ${err.message}`)
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
  
  jobs.forEach(job => {
    if (job.status === 'Done') doneCount++
    else if (job.failed || job.status?.startsWith('Failed')) failedCount++
    else if (job.status === 'Queued') queuedCount++
    else runningCount++
  })

  let globalEtaStr = "--"
  const ges = batchData?.global_eta_seconds
  if (inProgress && runningCount > 0 && ges != null && ges > 0) {
    const m = Math.floor(ges / 60)
    const s = Math.floor(ges % 60)
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
        
          <div className="flex items-center gap-3 bg-secondary/50 border border-border rounded-xl p-2 shrink-0 shadow-sm flex-wrap">
          <div className="flex items-center gap-2 px-2">
            <label className="text-sm font-medium">Quantity</label>
            <select
              className="w-16 bg-background border border-border rounded-md px-2 py-1 text-sm text-center appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              value={numShorts}
              onChange={(e) => {
                updateAppState({ batch_num_shorts: parseInt(e.target.value) })
                saveCurrentState()
              }}
              disabled={inProgress}
            >
              {[1,2,3,4,5,10,15,20,25,30,40,50].map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
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
                        <span className="text-xs text-muted-foreground mt-1 line-clamp-3" title={availablePrompts[key]}>{availablePrompts[key]}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => setEnableEmojis(!enableEmojis)}
            disabled={inProgress}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all border ${
              enableEmojis
                ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                : 'bg-muted/50 text-muted-foreground/60 border-border/30'
            } disabled:opacity-50`}
          >
            {enableEmojis ? '😊 Emoji' : '🚫 No Emoji'}
          </button>
          
          {enableEmojis && (
            <div className="flex items-center gap-2 bg-secondary/30 border border-border rounded-lg p-2 animate-in fade-in slide-in-from-top-2 duration-200 flex-wrap">
              <div className="flex items-center gap-2">
                <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Anim</label>
                <button
                  onClick={() => setEnableEmojiAnimation(!enableEmojiAnimation)}
                  className={`text-xs px-2 py-1 rounded font-medium transition-all border ${
                    enableEmojiAnimation
                      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                  }`}
                >
                  {enableEmojiAnimation ? 'On' : 'Off'}
                </button>
              </div>
              <div className="w-px h-5 bg-border" />
              <div className="flex items-center gap-1.5">
                <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Scale</label>
                <select
                  className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                  value={emojiScaleFactor}
                  onChange={(e) => {
                    updateAppState({ emoji_scale_factor: parseFloat(e.target.value) })
                    saveCurrentState()
                  }}
                >
                  {[0.5,1.0,1.5,2.0,2.5,3.0].map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div className="w-px h-5 bg-border" />
              <div className="flex items-center gap-1.5">
                <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Hold</label>
                <select
                  className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                  value={emojiHoldDuration}
                  onChange={(e) => {
                    updateAppState({ emoji_hold_duration: parseFloat(e.target.value) })
                    saveCurrentState()
                  }}
                >
                  {[0,0.5,1.0,1.5,2.0].map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div className="w-px h-5 bg-border" />
              <div className="flex items-center gap-1.5">
                <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Max/Word</label>
                <select
                  className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                  value={emojiThrowMaxCount}
                  onChange={(e) => {
                    updateAppState({ emoji_throw_max_count: parseInt(e.target.value) })
                    saveCurrentState()
                  }}
                >
                  {[1,3,5,10,15,20].map(n => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div className="w-px h-5 bg-border" />
              <div className="flex items-center gap-1.5">
                <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Styles</label>
                <div className="flex bg-background border border-border rounded-md overflow-hidden">
                  {AVAILABLE_EMOJI_STYLES.map(style => {
                    const active = emojiStyles.includes(style.id)
                    return (
                      <button
                        key={style.id}
                        onClick={() => {
                          if (active && emojiStyles.length > 1) {
                            setEmojiStyles(emojiStyles.filter(s => s !== style.id))
                          } else if (!active) {
                            setEmojiStyles([...emojiStyles, style.id])
                          }
                        }}
                        className={`text-[10px] px-1.5 py-1 font-medium transition-colors border-r border-border last:border-0 ${
                          active ? 'bg-blue-500/20 text-blue-500' : 'text-muted-foreground hover:bg-secondary'
                        }`}
                      >
                        {style.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

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
                <span className="text-foreground font-bold">{doneCount}/{totalJobs} completed</span>
                {inProgress && (
                  <span className="text-purple-400 flex items-center gap-1 font-bold bg-purple-500/10 px-2 py-0.5 rounded-md border border-purple-500/20 shadow-[0_0_10px_rgba(168,85,247,0.2)] animate-in fade-in">
                    ETA: {globalEtaStr}
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {!inProgress && failedCount > 0 && (
              <button 
                onClick={handleRetryFailed}
                disabled={isRetrying}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-xs transition-all bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border border-amber-500/20 disabled:opacity-50"
              >
                <RefreshCw size={14} className={isRetrying ? "animate-spin" : ""} />
                {isRetrying ? "Retrying..." : `Retry Failed (${failedCount})`}
              </button>
            )}
            {!inProgress && jobs.length > 0 && (
              <button 
                onClick={handleDownloadReport}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-xs transition-all bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border border-emerald-500/20"
              >
                <Download size={14} />
                Download Report
              </button>
            )}
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
        </div>

        {connectionError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-400 text-sm font-medium mx-4 mt-4 mb-0">
            Lost connection to server — progress may be stale
          </div>
        )}

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
          {initialLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse bg-secondary/40 rounded-xl h-32" />
              ))}
            </div>
          ) : jobs.length > 0 ? (
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
                  <div key={job.id} onClick={() => setSelectedJobId(job.id)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') setSelectedJobId(job.id) }} className="bg-background border border-border/50 rounded-xl p-4 flex flex-col gap-3 shadow-sm hover:border-blue-500/30 hover:shadow-[0_4px_20px_-4px_rgba(59,130,246,0.1)] transition-all duration-300 relative overflow-hidden backdrop-blur-sm cursor-pointer">
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
                        <span className={`ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          job.enable_emojis
                            ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                            : 'bg-muted/50 text-muted-foreground/60 border border-border/30'
                        }`}>
                          {job.enable_emojis ? '😊 Emoji' : '🚫 No Emoji'}
                        </span>
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
                          <MultiSegmentProgressBar progress={p} segments={batchData?.progress_segments} />
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
      {selectedJobId && (
        <JobDetailModal
          job={jobDetail}
          onClose={() => setSelectedJobId(null)}
          progress={batchData?.progress_segments}
        />
      )}
    </div>
  )
}

const DEFAULT_SEGMENTS = []

const SEGMENT_GRADIENTS = [
  { from: 'from-pink-500 to-rose-500', shadow: 'rgba(236,72,153,0.6)' },
  { from: 'from-rose-500 to-amber-500', shadow: 'rgba(245,158,11,0.6)' },
  { from: 'from-amber-500 to-emerald-500', shadow: 'rgba(16,185,129,0.6)' },
  { from: 'from-emerald-500 to-cyan-500', shadow: 'rgba(6,182,212,0.6)' },
]

const MultiSegmentProgressBar = ({ progress, segments }) => {
  const segs = segments && segments.length > 0 ? segments : DEFAULT_SEGMENTS

  if (segs.length === 0) {
    return (
      <div className="w-full h-2 rounded-full overflow-hidden bg-background/50 border border-border/50">
        <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-300 ease-out rounded-full" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
      </div>
    )
  }

  return (
    <div className="w-full flex gap-1 h-2 rounded-full overflow-hidden bg-background/50 border border-border/50">
      {segs.map((seg, i) => {
        const flex = seg.end - seg.start
        const fill = Math.min(100, Math.max(0, ((progress - seg.start) / (seg.end - seg.start)) * 100))
        const gradient = SEGMENT_GRADIENTS[i % SEGMENT_GRADIENTS.length]
        return (
          <div key={seg.name || i} className="h-full bg-secondary/40" style={{ flex }}>
            <div className={`h-full bg-gradient-to-r ${gradient.from} transition-all duration-300 ease-out`} style={{ width: `${fill}%`, boxShadow: `0 0 8px ${gradient.shadow}` }} />
          </div>
        )
      })}
    </div>
  )
}

const JobDetailModal = ({ job, onClose, progress }) => {
  if (!job) return null

  const isDone = job.status === 'Done'
  const isFailed = job.failed || job.status?.startsWith('Failed')
  const isQueued = job.status === 'Queued'
  const isRunning = !isDone && !isFailed && !isQueued

  const p = job.progress || 0

  const statusBadge = (status, icon, color) => (
    <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold border ${color}`}>
      {icon} {status}
    </span>
  )

  // Helper for settings rows
  const SettingRow = ({ label, value }) => (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-b-0">
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
      <span className="text-xs text-foreground font-mono">{value ?? '—'}</span>
    </div>
  )

  const Section = ({ title, icon, children }) => (
    <div className="bg-secondary/20 border border-border/40 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-3">{icon} {title}</h3>
      <div className="divide-y divide-border/20">
        {children}
      </div>
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border bg-secondary/20 shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold">Job #{job.id}</h2>
            {isDone && statusBadge('Done', <CheckCircle2 size={14} />, 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10')}
            {isFailed && statusBadge('Failed', <XCircle size={14} />, 'text-red-400 border-red-500/30 bg-red-500/10')}
            {isQueued && statusBadge('Queued', <Clock size={14} />, 'text-muted-foreground border-border bg-muted/30')}
            {isRunning && statusBadge('Running', <Loader2 size={14} className="animate-spin" />, 'text-blue-400 border-blue-500/30 bg-blue-500/10')}
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-secondary/50 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Topic */}
          <div>
            <p className="text-sm text-muted-foreground font-medium mb-1">Topic</p>
            <p className="text-sm font-semibold">{job.topic || 'Waiting for topic...'}</p>
            <p className="text-xs text-muted-foreground mt-1">{job.voice_name || '—'} · {job.layout || '—'}</p>
          </div>

          {/* Progress Section */}
          <Section title="Progress" icon={<Activity size={16} className="text-blue-400" />}>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs font-medium text-blue-400">{job.status}</span>
                <span className="text-xs font-bold">{p}%</span>
              </div>
              <MultiSegmentProgressBar progress={p} segments={progress} />
              <div className="flex gap-4">
                <SettingRow label="Elapsed" value={job.elapsed} />
                <SettingRow label="ETA" value={job.eta} />
              </div>
            </div>
          </Section>

          {/* AI Settings */}
          <Section title="AI Settings" icon={<Sparkles size={16} className="text-purple-400" />}>
            <SettingRow label="Model" value={job.model || '—'} />
            <SettingRow label="Script Temp" value={job.script_temp || '—'} />
            <SettingRow label="Meta Temp" value={job.meta_temp || '—'} />
            <SettingRow label="Max Words" value={job.settings?.max_words || '—'} />
          </Section>

          {/* Text / Subtitles */}
          <Section title="Text &amp; Subtitles" icon={<Type size={16} className="text-amber-400" />}>
            <SettingRow label="Font" value={job.sub_font || '—'} />
            <SettingRow label="Font Size" value={job.sub_size ? `${job.sub_size}px` : '—'} />
            <SettingRow label="Color" value={job.sub_color || '—'} />
            <SettingRow label="Highlight" value={job.sub_highlight || '—'} />
            <SettingRow label="Outline" value={job.sub_outline || '—'} />
            <SettingRow label="Outline Width" value={job.sub_outline_width || '—'} />
            <SettingRow label="Bold" value={job.sub_bold ? 'Yes' : 'No'} />
            <SettingRow label="Uppercase" value={job.sub_uppercase ? 'Yes' : 'No'} />
            <SettingRow label="Animation" value={job.sub_animation_style || '—'} />
            <SettingRow label="Words / Screen" value={job.words_per_screen || '—'} />
            <SettingRow label="Word Pop" value={job.word_pop ? `Yes (${job.word_pop_scale}x)` : 'No'} />
            <SettingRow label="Inactive Dim" value={job.inactive_dim ? `Yes (${job.inactive_alpha})` : 'No'} />
            <SettingRow label="Single Word" value={job.single_word_mode ? 'Yes' : 'No'} />
            <SettingRow label="Border Style" value={job.sub_border_style || '—'} />
            <SettingRow label="Shadow Width" value={job.sub_shadow_width || '—'} />
            <SettingRow label="BG Color" value={job.sub_bg_color || '—'} />
            <SettingRow label="BG Alpha" value={job.sub_bg_alpha || '—'} />
          </Section>

          {/* Emoji Settings */}
          <Section title="Emoji" icon={<Smile size={16} className="text-yellow-400" />}>
            <SettingRow label="Enabled" value={job.enable_emojis ? 'Yes' : 'No'} />
            <SettingRow label="Animation" value={job.enable_emoji_animation ? 'On' : 'Off'} />
            <SettingRow label="Scale" value={job.emoji_scale_factor || '—'} />
            <SettingRow label="Hold Duration" value={job.emoji_hold_duration ? `${job.emoji_hold_duration}s` : '—'} />
            <SettingRow label="Max / Word" value={job.emoji_throw_max_count || '—'} />
            <SettingRow label="Position" value={job.emoji_position || '—'} />
            <SettingRow label="Style" value={job.emoji_style || '—'} />
          </Section>

          {/* Audio Settings */}
          <Section title="Audio" icon={<Volume2 size={16} className="text-green-400" />}>
            <SettingRow label="Voice" value={job.voice_name || job.voice_id || '—'} />
            <SettingRow label="Voice Speed" value={job.voice_speed || '—'} />
            <SettingRow label="Music Volume" value={job.music_volume || '—'} />
            <SettingRow label="Voice Volume" value={job.voice_volume || '—'} />
          </Section>

          {/* Video Settings */}
          <Section title="Video" icon={<Film size={16} className="text-rose-400" />}>
            <SettingRow label="Layout" value={job.layout || '—'} />
            <SettingRow label="Output" value={job.output_filename || '—'} />
          </Section>

          {/* Generated Content (only if available) */}
          {(job.generated_title || job.generated_hashtags || job.script_text) && (
            <Section title="Generated Content" icon={<FileText size={16} className="text-emerald-400" />}>
              {job.generated_title && <SettingRow label="Title" value={job.generated_title} />}
              {job.generated_hashtags && <SettingRow label="Hashtags" value={job.generated_hashtags} />}
              {job.script_text && (
                <div className="py-2">
                  <span className="text-xs text-muted-foreground font-medium">Script</span>
                  <pre className="text-xs text-foreground mt-1 whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-48 overflow-y-auto font-mono leading-relaxed">{job.script_text}</pre>
                </div>
              )}
            </Section>
          )}

          {/* Prompt (system prompt) */}
          {job.system_prompt && (
            <Section title="System Prompt" icon={<MessageSquare size={16} className="text-indigo-400" />}>
              <pre className="text-xs text-foreground whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-40 overflow-y-auto font-mono leading-relaxed">{job.system_prompt}</pre>
            </Section>
          )}

          {/* Raw Prompt */}
          {job.prompt && (
            <Section title="Generation Prompt" icon={<Terminal size={16} className="text-cyan-400" />}>
              <pre className="text-xs text-foreground whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-32 overflow-y-auto font-mono leading-relaxed">{job.prompt}</pre>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
