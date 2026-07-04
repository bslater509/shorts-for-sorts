import { useState, useEffect, useCallback } from 'react'
import { Layers, Play, Square, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Batch() {
  const [numShorts, setNumShorts] = useState(5)
  const [batchData, setBatchData] = useState(null) // { in_progress, num_shorts, jobs: [] }
  const [isPolling, setIsPolling] = useState(false)
  const [isStarting, setIsStarting] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getBatchStatus()
      setBatchData(data)
      if (data.in_progress && !isPolling) {
        setIsPolling(true)
      } else if (!data.in_progress && isPolling) {
        setIsPolling(false)
      }
    } catch (err) {
      console.error("Failed to fetch batch status", err)
    }
  }, [isPolling])

  // Initial check
  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Polling
  useEffect(() => {
    let interval = null
    if (isPolling) {
      interval = setInterval(() => {
        fetchStatus()
      }, 1000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isPolling, fetchStatus])

  const handleStart = async () => {
    if (numShorts < 1) return
    setIsStarting(true)
    try {
      await api.startBatch(numShorts)
      setIsPolling(true)
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

  jobs.forEach(job => {
    if (job.status === 'Done') doneCount++
    else if (job.failed || job.status.startsWith('Failed')) failedCount++
    else if (job.status === 'Queued') queuedCount++
    else runningCount++
  })

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
          <button 
            onClick={handleStart}
            disabled={inProgress || isStarting}
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
              <span className={cn("flex h-3 w-3 rounded-full", inProgress ? "bg-blue-500 animate-pulse" : "bg-muted-foreground")} />
              {inProgress ? 'Batch Running...' : 'Idle'}
            </div>
            
            {batchData && (
              <div className="flex flex-wrap items-center gap-3 text-sm font-medium sm:border-l border-border sm:pl-4">
                <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 size={14}/> {doneCount} Done</span>
                <span className="text-blue-500 flex items-center gap-1"><Loader2 size={14} className={cn(runningCount > 0 && "animate-spin")}/> {runningCount} Running</span>
                <span className="text-red-500 flex items-center gap-1"><XCircle size={14}/> {failedCount} Failed</span>
                <span className="text-muted-foreground flex items-center gap-1"><Clock size={14}/> {queuedCount} Queued</span>
                <span className="text-foreground ml-2">Total: {totalJobs}</span>
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

        {/* Jobs Grid */}
        <div className="flex-1 md:overflow-y-auto p-6 bg-secondary/10">
          {jobs.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {jobs.map((job) => {
                const isDone = job.status === 'Done'
                const isFailed = job.failed || job.status.startsWith('Failed')
                const isQueued = job.status === 'Queued'
                const isRunning = !isDone && !isFailed && !isQueued
                const p = job.progress || 0

                return (
                  <div key={job.id} className="bg-background border border-border rounded-xl p-4 flex flex-col gap-3 shadow-sm hover:border-blue-500/30 transition-colors">
                    <div className="flex justify-between items-start">
                      <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Job #{job.id}</span>
                      <span className="text-xs font-medium text-muted-foreground bg-secondary px-2 py-0.5 rounded-md">{job.elapsed}</span>
                    </div>
                    
                    <div className="space-y-1">
                      <h4 className="font-semibold text-sm leading-tight line-clamp-2" title={job.topic}>
                        {job.topic || "Generating topic..."}
                      </h4>
                      <p className="text-xs text-muted-foreground">
                        {job.voice || "Auto Voice"} • {job.layout || "Auto Layout"}
                      </p>
                    </div>

                    <div className="mt-auto pt-3 border-t border-border">
                      {isDone && <span className="text-emerald-500 text-sm font-semibold flex items-center gap-1"><CheckCircle2 size={16}/> Completed</span>}
                      {isFailed && <span className="text-red-500 text-sm font-semibold flex items-center gap-1"><XCircle size={16}/> {job.status}</span>}
                      {isQueued && <span className="text-muted-foreground text-sm font-medium flex items-center gap-1"><Clock size={16}/> Queued...</span>}
                      
                      {isRunning && (
                        <div className="space-y-2">
                          <div className="flex justify-between text-xs font-medium">
                            <span className="text-blue-500 truncate pr-2">{job.status}</span>
                            <span className="text-foreground shrink-0">{p}%</span>
                          </div>
                          <div className="w-full bg-secondary rounded-full h-1.5 overflow-hidden">
                            <div className="bg-blue-500 h-full transition-all duration-300 ease-out" style={{ width: `${p}%` }} />
                          </div>
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
