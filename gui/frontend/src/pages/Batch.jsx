import { useState, useEffect, useCallback } from 'react'
import { Square, Loader2, CheckCircle2, XCircle, Clock, RefreshCw, Download, Layers, Ban, Zap, Sparkles, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import { toast } from 'sonner'
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
  const [isRetryingCancelled, setIsRetryingCancelled] = useState(false)
  const [connectionError, setConnectionError] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [enableEmojis, setEnableEmojis] = useState(true)
  const [enableEmojiAnimation, setEnableEmojiAnimation] = useState(true)

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
    if (selectedPrompts.length === 0) {
      toast.error("No prompts selected", { description: "Please select at least one prompt template." })
      return
    }
    setIsStarting(true)
    try {
      await api.startBatch(numShorts, selectedPrompts, enableEmojis,
          enableEmojiAnimation, emojiScaleFactor, emojiHoldDuration,
          emojiThrowMaxCount)
      toast.success("Batch started", { description: `Generating ${numShorts} videos across ${selectedPrompts.length} prompt sets.` })
      fetchStatus()
    } catch (err) {
      toast.error("Failed to start batch", { description: err.message })
    } finally {
      setIsStarting(false)
    }
  }

  const handleCancel = async () => {
    try {
      await api.cancelBatch()
      toast.info("Cancellation requested", { description: "The batch will stop once current jobs finish." })
    } catch (err) {
      toast.error("Cancel failed", { description: err.message })
    }
  }

  const handleRetryFailed = async () => {
    setIsRetrying(true)
    try {
      await api.retryFailedBatch()
      toast.success("Retrying failed jobs", { description: `${failedCount} job(s) will be re-generated.` })
      setIsRetrying(false)
    } catch (err) {
      toast.error("Retry failed", { description: err.message })
      setIsRetrying(false)
    }
  }

  const handleRetryJob = async (jobId) => {
    setIsRetryingJob(jobId)
    try {
      await api.retryBatchJob(jobId)
      toast.success(`Job #${jobId} queued for retry`, { description: "It will be re-generated shortly." })
      setIsRetryingJob(null)
    } catch (err) {
      toast.error(`Retry job #${jobId} failed`, { description: err.message })
      setIsRetryingJob(null)
    }
  }

  const handleRetryCancelled = async () => {
    setIsRetryingCancelled(true)
    try {
      await api.retryCancelledBatch()
      toast.success("Retrying cancelled jobs", { description: `${cancelledCount} job(s) will be re-generated.` })
    } catch (err) {
      toast.error("Retry cancelled failed", { description: err.message })
    } finally {
      setIsRetryingCancelled(false)
    }
  }

  const handleCancelQueued = async (jobId) => {
    try {
      await api.cancelJob(jobId)
      toast.info(`Job #${jobId} cancelled`, { description: "The queued job has been removed." })
      fetchStatus()
    } catch (err) {
      toast.error(`Cancel job #${jobId} failed`, { description: err.message })
    }
  }

  const handleDismiss = async (jobId) => {
    try {
      await api.dismissJob(jobId)
      fetchStatus()
    } catch (err) {
      console.error(`Dismiss job #${jobId} failed:`, err)
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
      toast.success("Report downloaded", { description: "Batch report saved as JSON." })
    } catch (err) {
      toast.error("Failed to download report", { description: err.message })
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
  let cancelledCount = 0
  
  jobs.forEach(job => {
    if (job.status === 'Done') doneCount++
    else if (job.cancelled || job.status === 'Cancelled') cancelledCount++
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
    <div className="space-y-3 md:space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)]">
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
        handleStart={handleStart}
        isStarting={isStarting}
      />

        <div className="flex-1 bg-card border border-border rounded-xl shadow-sm md:overflow-hidden flex flex-col">
        {/* Status Header */}
        <div className="bg-secondary/30 border-b border-border px-3 py-2 md:px-4 md:py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-sm font-medium">
              <span className={cn("flex h-2.5 w-2.5 rounded-full", inProgress ? "bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]" : "bg-muted-foreground")} />
              {inProgress ? 'Batch Running...' : 'Idle'}
            </div>
            
            {batchData && (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs md:text-sm font-medium">
                <span className="text-emerald-500 flex items-center gap-0.5"><CheckCircle2 size={12}/> {doneCount}</span>
                <span className="text-blue-500 flex items-center gap-0.5"><Loader2 size={12} className={cn(runningCount > 0 && "animate-spin")}/> {runningCount}</span>
                <span className="text-orange-500 flex items-center gap-0.5"><Ban size={12}/> {cancelledCount}</span>
                <span className="text-red-500 flex items-center gap-0.5"><XCircle size={12}/> {failedCount}</span>
                <span className="text-muted-foreground flex items-center gap-0.5"><Clock size={12}/> {queuedCount}</span>
                <span className="text-foreground font-semibold">{doneCount}/{totalJobs}</span>
                {inProgress && (
                  <span className="text-purple-400 flex items-center gap-1 font-bold bg-purple-500/10 px-1.5 py-0.5 rounded-md border border-purple-500/20 shadow-[0_0_10px_rgba(168,85,247,0.2)] animate-in fade-in text-[10px] md:text-xs">
                    ETA: {globalEtaStr}
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-1.5 flex-wrap">
            {!inProgress && failedCount > 0 && (
              <Button 
                onClick={handleRetryFailed}
                disabled={isRetrying}
                variant="outline"
                className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 text-[10px] md:text-xs px-2 py-1 h-auto"
              >
                <RefreshCw size={10} className={isRetrying ? "animate-spin" : ""} />
                {isRetrying ? "Retrying..." : `Retry Failed (${failedCount})`}
              </Button>
            )}
            {!inProgress && cancelledCount > 0 && (
              <Button 
                onClick={handleRetryCancelled}
                disabled={isRetryingCancelled}
                variant="outline"
                className="bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border-orange-500/20 text-[10px] md:text-xs px-2 py-1 h-auto"
              >
                <RefreshCw size={10} className={isRetryingCancelled ? "animate-spin" : ""} />
                {isRetryingCancelled ? "Retrying..." : `Retry Cancelled (${cancelledCount})`}
              </Button>
            )}
            {!inProgress && jobs.length > 0 && (
              <Button 
                onClick={handleDownloadReport}
                variant="outline"
                className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 text-[10px] md:text-xs px-2 py-1 h-auto"
              >
                <Download size={10} />
                Download Report
              </Button>
            )}
            {inProgress && (
              <Button 
                onClick={handleCancel}
                variant="outline"
                className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20 text-[10px] md:text-xs px-2 py-1 h-auto"
              >
                <Square size={10} />
                Cancel Batch
              </Button>
            )}
          </div>
        </div>

        {connectionError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-400 text-xs font-medium mx-3 mt-2 mb-0 flex items-center gap-2 animate-in fade-in slide-in-from-top-2 duration-300">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
            </span>
            <span>Lost connection to server —&nbsp;progress may be stale. Reconnecting...</span>
          </div>
        )}

        {/* System Stats Charts */}
        <SystemStatsCharts systemStats={systemStats} />

        {/* Jobs Grid */}
        <div className="flex-1 md:overflow-y-auto p-3 md:p-4 bg-secondary/10 overscroll-contain touch-pan-y">
          {initialLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse bg-secondary/40 rounded-xl h-28" />
              ))}
            </div>
          ) : jobs.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...jobs].sort((a, b) => {
                if (a.status === 'Done' && b.status !== 'Done') return 1;
                if (b.status === 'Done' && a.status !== 'Done') return -1;
                return (b.progress || 0) - (a.progress || 0);
              }).map((job, index) => (
                <JobCard
                  key={job.id}
                  job={job}
                  index={index}
                  onClick={() => setSelectedJobId(job.id)}
                  progressSegments={batchData?.progress_segments}
                  onRetry={!inProgress ? handleRetryJob : null}
                  onDismiss={!inProgress ? handleDismiss : null}
                  onCancelQueued={inProgress ? handleCancelQueued : null}
                />
              ))}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground space-y-3 py-16">
              <div className="relative">
                <Layers size={48} className="opacity-10" />
                <Sparkles size={20} className="absolute -top-1 -right-1 text-blue-400/30 animate-pulse" />
                <Zap size={16} className="absolute -bottom-1 -left-1 text-purple-400/30 animate-pulse delay-500" />
              </div>
              <div className="space-y-1 max-w-xs">
                <p className="text-sm font-medium text-foreground/60">No batch jobs yet</p>
                <p className="text-xs text-muted-foreground/60 leading-relaxed">
                  Configure your settings above, choose your prompt templates, then hit <span className="text-blue-400 font-semibold">Start Batch</span> to generate multiple videos autonomously.
                </p>
              </div>
              {!inProgress && (
                <Button
                  variant="outline"
                  onClick={() => {
                    const header = document.querySelector('header')
                    header?.scrollIntoView({ behavior: 'smooth' })
                  }}
                  className="text-xs gap-1.5 mt-2 bg-blue-500/5 border-blue-500/20 text-blue-400 hover:bg-blue-500/10"
                >
                  <Play size={12} />
                  Get Started
                </Button>
              )}
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
