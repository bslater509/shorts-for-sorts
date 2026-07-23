import { useState, useEffect, useCallback } from 'react'
import { Square, Loader2, CheckCircle2, XCircle, Clock, RefreshCw, Download, Layers } from 'lucide-react'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import BatchHeader from '@/components/batch/BatchHeader'
import JobCard from '@/components/batch/JobCard'
import JobDetailModal from '@/components/batch/JobDetailModal'
import SystemStatsCharts from '@/components/batch/SystemStatsCharts'

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
  const [isRetryingJob, setIsRetryingJob] = useState(null)
  const [connectionError, setConnectionError] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [enableEmojis, setEnableEmojis] = useState(true)
  const [enableEmojiAnimation, setEnableEmojiAnimation] = useState(true)
  const [emojiStyles, setEmojiStyles] = useState(['apple', 'twemoji'])

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

  const handleRetryJob = async (jobId) => {
    setIsRetryingJob(jobId)
    try {
      await api.retryBatchJob(jobId)
      setIsRetryingJob(null)
    } catch (err) {
      alert(`Retry job #${jobId} failed: ${err.message}`)
      setIsRetryingJob(null)
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
      <BatchHeader
        availablePrompts={availablePrompts}
        selectedPrompts={selectedPrompts}
        setSelectedPrompts={setSelectedPrompts}
        showPromptDropdown={showPromptDropdown}
        setShowPromptDropdown={setShowPromptDropdown}
        numShorts={numShorts}
        inProgress={inProgress}
        updateAppState={updateAppState}
        saveCurrentState={saveCurrentState}
        enableEmojis={enableEmojis}
        setEnableEmojis={setEnableEmojis}
        enableEmojiAnimation={enableEmojiAnimation}
        setEnableEmojiAnimation={setEnableEmojiAnimation}
        emojiScaleFactor={emojiScaleFactor}
        emojiHoldDuration={emojiHoldDuration}
        emojiThrowMaxCount={emojiThrowMaxCount}
        emojiStyles={emojiStyles}
        setEmojiStyles={setEmojiStyles}
        handleStart={handleStart}
        isStarting={isStarting}
      />

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
        <SystemStatsCharts systemStats={systemStats} />

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
              }).map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onClick={() => setSelectedJobId(job.id)}
                  progressSegments={batchData?.progress_segments}
                  onRetry={!inProgress ? handleRetryJob : null}
                />
              ))}
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
