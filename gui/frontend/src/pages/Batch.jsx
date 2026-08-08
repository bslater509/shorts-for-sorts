import { useState, useEffect, useCallback, useRef } from 'react'
import { Square, Loader2, CheckCircle2, XCircle, Clock, RefreshCw, Download, Layers, Ban, Zap, Sparkles, Play, FolderOpen, FileVideo } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import { toast } from 'sonner'
import BatchHeader from '@/components/batch/BatchHeader'
import JobCard from '@/components/batch/JobCard'
import JobDetailModal from '@/components/batch/JobDetailModal'
import SystemStatsCharts from '@/components/batch/SystemStatsCharts'

const FILTER_TABS = ['All', 'Running', 'Queued', 'Done', 'Failed', 'Cancelled']

const TAB_EMPTY_STATES = {
  All: { title: 'All jobs hidden', desc: 'All jobs in this batch have been dismissed.' },
  Running: { title: 'No running jobs', desc: 'Jobs actively processing will appear here.' },
  Queued: { title: 'No queued jobs', desc: 'Jobs waiting for a free worker slot.' },
  Done: { title: 'No completed jobs', desc: 'Finished videos will appear here.' },
  Failed: { title: 'No failed jobs', desc: 'Jobs that need a retry will appear here.' },
  Cancelled: { title: 'No cancelled jobs', desc: 'Cancelled jobs will appear here.' },
}

function formatSize(bytes) {
  if (!bytes) return null
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function formatDuration(secs) {
  if (!secs) return null
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function Batch() {
  const defaultBatchSize = useAppStore((s) => s.settings?.default_batch_size) || 1
  const numShorts = useAppStore((s) => s.appState?.batch_num_shorts || defaultBatchSize)
  const emojiScaleFactor = useAppStore((s) => s.appState?.emoji_scale_factor || 1.5)
  const emojiHoldDuration = useAppStore((s) => s.appState?.emoji_hold_duration || 0.5)
  const emojiThrowMaxCount = useAppStore((s) => s.appState?.emoji_throw_max_count || 3)

  // Advanced batch generation options (persisted in appState, see BatchHeader)
  const batchLayout = useAppStore((s) => s.appState?.batch_layout ?? 'Random')
  const batchVoiceId = useAppStore((s) => s.appState?.batch_voice_id ?? 'Random')
  const batchSubAnimationStyle = useAppStore((s) => s.appState?.batch_sub_animation_style ?? 'Random')
  const batchWordsPerScreen = useAppStore((s) => s.appState?.batch_words_per_screen ?? 'Default')
  const batchSingleWordMode = useAppStore((s) => s.appState?.batch_single_word_mode ?? false)
  const batchBgMusicPath = useAppStore((s) => s.appState?.batch_bg_music_path ?? 'Random')
  const batchScriptTemp = useAppStore((s) => s.appState?.batch_script_temp ?? s.settings?.llm_temp_script ?? 0.7)
  const batchMetaTemp = useAppStore((s) => s.appState?.batch_meta_temp ?? s.settings?.llm_temp_metadata ?? 0.7)
  const batchMaxWorkers = useAppStore((s) => s.appState?.batch_max_workers ?? s.settings?.max_workers ?? 1)
  const batchLlmMaxWorkers = useAppStore((s) => s.appState?.batch_llm_max_workers ?? s.settings?.llm_max_workers ?? 5)
  const batchPostToTikTok = useAppStore((s) => s.appState?.batch_post_to_tiktok ?? false)
  const updateAppState = useAppStore((s) => s.updateAppState)
  const saveCurrentState = useAppStore((s) => s.saveCurrentState)
  const [batchData, setBatchData] = useState(null)
  const [systemStats, setSystemStats] = useState([])
  const [isStarting, setIsStarting] = useState(false)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [jobDetail, setJobDetail] = useState(null)

  const [streamingScripts, setStreamingScripts] = useState({})

  const [availablePrompts, setAvailablePrompts] = useState({})
  const [selectedPrompts, setSelectedPrompts] = useState([])
  const [showPromptDropdown, setShowPromptDropdown] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [isRetryingCancelled, setIsRetryingCancelled] = useState(false)
  const [connectionError, setConnectionError] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [enableEmojis, setEnableEmojis] = useState(true)
  const [enableEmojiAnimation, setEnableEmojiAnimation] = useState(true)

  const [filterTab, setFilterTab] = useState('All')
  const wsConnectedRef = useRef(false)

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
        const newStats = [...prev, {
          time: Date.now(),
          cpu: data.cpu_percent || 0,
          ram: data.memory_percent || 0,
          disk: data.disk_percent || 0,
          rss: data.rss_mb || 0,
          netRecv: data.net_recv_kbs || 0,
          netSent: data.net_sent_kbs || 0,
          swap: data.swap_percent || 0,
          load: data.load_avg || 0,
        }]
        if (newStats.length > 30) newStats.shift()
        return newStats
      })
    } catch (err) {
      console.debug("Failed to fetch batch status", err)
      setConnectionError(true)
      setInitialLoading(false)
    }
  }, [])

  // WS-driven updates: listen for batch-status events, fallback polling
  useEffect(() => {
    const wsHandler = (e) => {
      wsConnectedRef.current = true
      const payload = e.detail
      setBatchData(payload)
      setSystemStats(prev => {
        const newStats = [...prev, {
          time: Date.now(),
          cpu: payload.cpu_percent || 0,
          ram: payload.memory_percent || 0,
          disk: payload.disk_percent || 0,
          rss: payload.rss_mb || 0,
          netRecv: payload.net_recv_kbs || 0,
          netSent: payload.net_sent_kbs || 0,
          swap: payload.swap_percent || 0,
          load: payload.load_avg || 0,
        }]
        if (newStats.length > 30) newStats.shift()
        return newStats
      })
    }
    window.addEventListener('batch-status', wsHandler)
    return () => window.removeEventListener('batch-status', wsHandler)
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(() => {
      if (!wsConnectedRef.current) {
        fetchStatus()
      } else {
        // Safety-net poll at 5s when connected
        fetchStatus()
      }
      wsConnectedRef.current = false
    }, wsConnectedRef.current ? 5000 : 1000)
    return () => clearInterval(interval)
  }, [fetchStatus])

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
    const jobFromBatch = batchData?.jobs?.find(j => j.id === selectedJobId)
    if (jobFromBatch?.status === 'Done') return
    const delay = batchData?.in_progress ? 1000 : 5000
    const interval = setInterval(fetchDetail, delay)
    return () => clearInterval(interval)
  }, [selectedJobId, batchData?.in_progress, batchData?.jobs])

  // Listen for LLM streaming events
  useEffect(() => {
    const handler = (e) => {
      const { event_type, job_id, token, word_count } = e.detail
      setStreamingScripts(prev => {
        if (event_type === "llm_started") {
          return { ...prev, [job_id]: { text: "", wordCount: 0, isActive: true } }
        }
        if (event_type === "llm_token") {
          const existing = prev[job_id] || { text: "", wordCount: 0, isActive: true }
          return { ...prev, [job_id]: { text: existing.text + token, wordCount: word_count, isActive: true } }
        }
        if (event_type === "llm_completed") {
          const existing = prev[job_id] || { text: "", wordCount: 0, isActive: false }
          return { ...prev, [job_id]: { ...existing, isActive: false, wordCount: word_count } }
        }
        return prev
      })
    }
    window.addEventListener("llm-stream", handler)
    return () => window.removeEventListener("llm-stream", handler)
  }, [])

  const handleStart = async () => {
    if (numShorts < 1) return
    if (selectedPrompts.length === 0) {
      toast.error("No prompts selected", { description: "Please select at least one prompt template." })
      return
    }
    try {
      const validation = await api.validateBatch()
      if (validation?.status === 'error') {
        const msg = validation.message || 'Validation failed'
        toast.error("Validation error", { description: msg })
        return
      }
      const warnings = validation?.warnings || []
      if (warnings.length > 0) {
        const proceed = window.confirm(
          `Pre-flight warnings (${warnings.length}):\n\n${warnings.join('\n')}\n\nDo you want to proceed anyway?`
        )
        if (!proceed) return
      }
    } catch (err) {
      console.debug("Validation request failed, proceeding anyway:", err)
    }
    setIsStarting(true)
    try {
      await api.startBatch(numShorts, selectedPrompts, {
        enableEmojis,
        enableEmojiAnimation,
        emojiScaleFactor,
        emojiHoldDuration,
        emojiThrowMaxCount,
        layout: batchLayout,
        voiceId: batchVoiceId,
        subAnimationStyle: batchSubAnimationStyle,
        wordsPerScreen: batchWordsPerScreen,
        singleWordMode: batchSingleWordMode,
        bgMusicPath: batchBgMusicPath,
        scriptTemp: batchScriptTemp,
        metaTemp: batchMetaTemp,
        maxWorkers: batchMaxWorkers,
        llmMaxWorkers: batchLlmMaxWorkers,
        postToTikTok: batchPostToTikTok,
      })
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
      toast.info("Cancelling batch", { description: "Stopping all running jobs now..." })
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
    try {
      await api.retryBatchJob(jobId)
      toast.success(`Job #${jobId} queued for retry`, { description: "It will be re-generated shortly." })
    } catch (err) {
      toast.error(`Retry job #${jobId} failed`, { description: err.message })
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
  const allJobs = batchData?.jobs || []
  const inProgress = batchData?.in_progress || false
  const totalJobs = batchData?.num_shorts || 0

  let doneCount = 0, runningCount = 0, failedCount = 0, queuedCount = 0, cancelledCount = 0

  allJobs.forEach(job => {
    if (job.dismissed) return
    if (job.status === 'Done') doneCount++
    else if (job.cancelled || job.status === 'Cancelled') cancelledCount++
    else if (job.failed || job.status?.startsWith('Failed')) failedCount++
    else if (job.status === 'Queued') queuedCount++
    else runningCount++
  })

  // Filter jobs
  const visibleJobs = allJobs.filter(job => {
    if (job.dismissed) return false
    switch (filterTab) {
      case 'Running': return !job.dismissed && job.status !== 'Done' && !job.cancelled && !job.failed && job.status !== 'Queued' && job.status !== 'Cancelled'
      case 'Queued': return job.status === 'Queued'
      case 'Done': return job.status === 'Done'
      case 'Failed': return job.failed || (job.status?.startsWith('Failed') && !job.cancelled && job.status !== 'Cancelled')
      case 'Cancelled': return job.cancelled || job.status === 'Cancelled'
      default: return true
    }
  })

  const tabCounts = {
    All: allJobs.filter(j => !j.dismissed).length,
    Running: allJobs.filter(j => !j.dismissed && j.status !== 'Done' && !j.cancelled && !j.failed && j.status !== 'Queued' && j.status !== 'Cancelled').length,
    Queued: queuedCount,
    Done: doneCount,
    Failed: failedCount,
    Cancelled: cancelledCount,
  }

  let globalEtaStr = "--"
  const ges = batchData?.global_eta_seconds
  if (inProgress && runningCount > 0 && ges != null && ges > 0) {
    const m = Math.floor(ges / 60)
    const s = Math.floor(ges % 60)
    globalEtaStr = m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  const isIdleWithResults = !inProgress && !initialLoading && allJobs.length > 0
  const doneJobs = allJobs.filter(j => j.status === 'Done')

  return (
    <div className="space-y-3 md:space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)] pb-28 md:pb-0">
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
        postToTikTok={batchPostToTikTok}
        onPostToTikTokChange={(v) => { updateAppState({ batch_post_to_tiktok: v }); saveCurrentState() }}
      />

      <div className="flex-1 bg-card border border-border rounded-xl shadow-sm md:overflow-hidden flex flex-col">
        {/* Status Header / Post-batch Summary */}
        <div className="bg-secondary/30 border-b border-border px-3 py-2 md:px-4 md:py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shrink-0">
          {isIdleWithResults ? (
            /* Post-batch summary panel */
            <>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                <span className="text-sm font-medium">Batch Results</span>
                <span className="text-xs text-muted-foreground">
                  <span className="text-emerald-500 font-semibold">{doneCount} done</span>
                  {failedCount > 0 && <span className="text-red-500 font-semibold"> · {failedCount} failed</span>}
                  {cancelledCount > 0 && <span className="text-orange-500 font-semibold"> · {cancelledCount} cancelled</span>}
                </span>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {failedCount > 0 && (
                  <Button onClick={handleRetryFailed} disabled={isRetrying} variant="outline"
                    className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <RefreshCw size={10} className={isRetrying ? "animate-spin" : ""} />
                    {isRetrying ? "Retrying..." : `Retry Failed (${failedCount})`}
                  </Button>
                )}
                {cancelledCount > 0 && (
                  <Button onClick={handleRetryCancelled} disabled={isRetryingCancelled} variant="outline"
                    className="bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border-orange-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <RefreshCw size={10} className={isRetryingCancelled ? "animate-spin" : ""} />
                    {isRetryingCancelled ? "Retrying..." : `Retry Cancelled (${cancelledCount})`}
                  </Button>
                )}
                <Button onClick={handleDownloadReport} variant="outline"
                  className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                  <Download size={10} /> Download Report
                </Button>
                {doneCount > 0 && (
                  <Button onClick={async () => { try { await api.openOutputFolder(); toast.success("Output folder opened") } catch (err) { toast.error("Failed to open folder", { description: err.message }) } }}
                    variant="outline" className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <FolderOpen size={10} /> Open Output Folder
                  </Button>
                )}
              </div>
            </>
          ) : (
            <>
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
                  <Button onClick={handleRetryFailed} disabled={isRetrying} variant="outline"
                    className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <RefreshCw size={10} className={isRetrying ? "animate-spin" : ""} />
                    {isRetrying ? "Retrying..." : `Retry Failed (${failedCount})`}
                  </Button>
                )}
                {!inProgress && cancelledCount > 0 && (
                  <Button onClick={handleRetryCancelled} disabled={isRetryingCancelled} variant="outline"
                    className="bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border-orange-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <RefreshCw size={10} className={isRetryingCancelled ? "animate-spin" : ""} />
                    {isRetryingCancelled ? "Retrying..." : `Retry Cancelled (${cancelledCount})`}
                  </Button>
                )}
                {!inProgress && allJobs.length > 0 && (
                  <Button onClick={handleDownloadReport} variant="outline"
                    className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <Download size={10} /> Download Report
                  </Button>
                )}
                {!inProgress && doneCount > 0 && (
                  <Button onClick={async () => { try { await api.openOutputFolder(); toast.success("Output folder opened") } catch (err) { toast.error("Failed to open folder", { description: err.message }) } }}
                    variant="outline" className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <FolderOpen size={10} /> Open Output Folder
                  </Button>
                )}
                {inProgress && (
                  <Button onClick={handleCancel} variant="outline"
                    className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20 text-[10px] md:text-xs px-2 py-1 h-auto">
                    <Square size={10} /> Cancel Batch
                  </Button>
                )}
              </div>
            </>
          )}
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

        {/* Filter Tabs */}
        {allJobs.length > 0 && (
          <div className="px-3 md:px-4 pt-2 flex items-center gap-1 overflow-x-auto shrink-0">
            {FILTER_TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setFilterTab(tab)}
                className={cn(
                  "px-2.5 py-1 min-h-[36px] md:min-h-[28px] text-[10px] md:text-xs font-medium rounded-md border transition-colors whitespace-nowrap flex items-center",
                  filterTab === tab
                    ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                    : "bg-transparent text-muted-foreground border-transparent hover:bg-secondary/50"
                )}
              >
                {tab} {tabCounts[tab] > 0 && <span className="ml-1 opacity-60">({tabCounts[tab]})</span>}
              </button>
            ))}
          </div>
        )}

        {/* Post-batch summary rows */}
        {isIdleWithResults && doneJobs.length > 0 && (
          <div className="px-3 md:px-4 py-2 border-b border-border/50 bg-secondary/10 shrink-0">
            <div className="flex flex-col gap-1">
              {doneJobs.map(job => (
                <div key={job.id} className="flex items-center gap-2 text-xs hover:bg-secondary/30 rounded px-1 py-0.5 transition-colors">
                  {job.thumbnail ? (
                    <img src={job.thumbnail} alt="" className="w-10 h-14 object-cover rounded border border-border/50 shrink-0" loading="lazy" />
                  ) : (
                    <div className="w-10 h-14 bg-secondary/50 rounded border border-border/50 shrink-0 flex items-center justify-center">
                      <FileVideo size={12} className="text-muted-foreground" />
                    </div>
                  )}
                  <span className="font-medium text-[11px] flex-1 min-w-0 truncate">{job.output_filename || `Job #${job.id}`}</span>
                  {job.size != null && <span className="text-[10px] text-muted-foreground whitespace-nowrap">{formatSize(job.size)}</span>}
                  {job.duration != null && <span className="text-[10px] text-muted-foreground whitespace-nowrap">{formatDuration(job.duration)}</span>}
                  {job.video_url && (
                    <>
                      <a href={job.video_url} target="_blank" rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 text-[10px] font-medium whitespace-nowrap"
                        onClick={e => e.stopPropagation()}>Play</a>
                      <a href={job.video_url} download
                        className="text-emerald-400 hover:text-emerald-300 text-[10px] font-medium whitespace-nowrap"
                        onClick={e => e.stopPropagation()}>Download</a>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Jobs Grid */}
        <div className="flex-1 md:overflow-y-auto p-3 md:p-4 bg-secondary/10 overscroll-contain touch-pan-y">
          {initialLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse bg-secondary/40 rounded-xl h-28" />
              ))}
            </div>
          ) : visibleJobs.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...visibleJobs].sort((a, b) => {
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
                  streamingScript={streamingScripts[job.id]}
                  onRetry={!inProgress ? handleRetryJob : null}
                  onDismiss={!inProgress ? handleDismiss : null}
                  onCancelQueued={inProgress ? handleCancelQueued : null}
                />
              ))}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground space-y-3 py-16">
              {allJobs.length === 0 ? (
                <>
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
                </>
              ) : (
                <>
                  <div className="relative mb-2">
                    <Layers size={40} className="opacity-10" />
                  </div>
                  <div className="space-y-1 max-w-xs">
                    <p className="text-sm font-medium text-foreground/60">
                      {TAB_EMPTY_STATES[filterTab]?.title || `No ${filterTab.toLowerCase()} jobs`}
                    </p>
                    <p className="text-xs text-muted-foreground/60 leading-relaxed">
                      {TAB_EMPTY_STATES[filterTab]?.desc || 'No jobs match this filter.'}
                    </p>
                  </div>
                  {filterTab !== 'All' && (
                    <Button
                      variant="outline"
                      onClick={() => setFilterTab('All')}
                      className="text-xs mt-3 bg-secondary/50 hover:bg-secondary/70 border-border/50 text-foreground/80 h-auto py-1.5 px-3"
                    >
                      View All Jobs
                    </Button>
                  )}
                </>
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
          streamingScript={streamingScripts[selectedJobId]}
        />
      )}

      {/* Mobile Sticky Action Bar */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-card/95 backdrop-blur-md border-t border-border p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.1)]">
        <Button
          variant="default"
          onClick={inProgress ? handleCancel : handleStart}
          disabled={isStarting || (!inProgress && selectedPrompts.length === 0)}
          className={`w-full flex items-center justify-center gap-2 py-6 rounded-xl font-bold text-sm shadow-md transition-all duration-200 ${
            inProgress
              ? 'bg-red-500 hover:bg-red-600 text-white shadow-red-500/25'
              : !isStarting && selectedPrompts.length > 0
                ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-blue-500/25'
                : ''
          }`}
        >
          {isStarting ? (
            <Loader2 size={16} className="animate-spin" />
          ) : inProgress ? (
            <Square size={16} />
          ) : (
            <Play size={16} />
          )}
          {isStarting ? 'Starting...' : inProgress ? 'Cancel Batch' : 'Start Batch'}
        </Button>
      </div>

    </div>
  )
}
