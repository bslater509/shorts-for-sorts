import { CheckCircle2, XCircle, Clock, RefreshCw, Ban, X, Square } from 'lucide-react'
import MultiSegmentProgressBar from './MultiSegmentProgressBar'
import { Button } from "@/components/ui/button"

const JobCard = ({ job, onClick, progressSegments, streamingScript, onRetry, onDismiss, onCancelQueued, index = 0 }) => {
  const isDone = job.status === 'Done'
  const isCancelled = job.cancelled || job.status === 'Cancelled'
  const isFailed = (job.failed || job.status?.startsWith('Failed')) && !isCancelled
  const isQueued = job.status === 'Queued'
  const isRunning = !isDone && !isFailed && !isQueued && !isCancelled
  const p = job.progress || 0

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick() }}
      className="group bg-background border border-border/50 rounded-xl p-3 flex flex-col gap-2 shadow-sm hover:border-blue-500/40 hover:shadow-[0_4px_24px_-4px_rgba(59,130,246,0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:border-blue-500/50 transition-all duration-300 relative overflow-hidden backdrop-blur-sm cursor-pointer animate-in fade-in slide-in-from-bottom-3 fill-mode-both"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      {/* Shimmer overlay for running jobs */}
      {isRunning && (
        <>
          <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 via-transparent to-transparent pointer-events-none" />
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-400/5 to-transparent pointer-events-none animate-shimmer" style={{ backgroundSize: '200% 100%' }} />
        </>
      )}

      {/* Hover glow accent */}
      <div className="absolute -inset-px rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5 pointer-events-none" />

      {/* Top row: topic + time badges */}
      <div className="flex items-start justify-between gap-2 relative">
        <h4 className="font-semibold text-sm leading-tight truncate flex-1 min-w-0" title={job.topic}>
          {job.topic || "Generating topic..."}
        </h4>
        <div className="flex gap-1.5 shrink-0">
          {job.eta && job.eta !== '--' && job.eta !== '0s' && (
            <span className="text-[10px] font-bold text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded-md border border-purple-500/20 shadow-[0_0_8px_rgba(168,85,247,0.15)] whitespace-nowrap">
              ETA: {job.eta}
            </span>
          )}
          <span className="text-[10px] font-medium text-muted-foreground bg-secondary/80 px-1.5 py-0.5 rounded-md border border-border/50 whitespace-nowrap">
            {job.elapsed}
          </span>
        </div>
      </div>

      {/* Meta row */}
      <p className="text-xs text-muted-foreground relative">
        {job.voice || "Auto Voice"} • {job.layout || "Auto Layout"}
        <span className={`ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
          job.enable_emojis
            ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
            : 'bg-muted/50 text-muted-foreground/60 border border-border/30'
        }`}>
          {job.enable_emojis ? '😊 Emoji' : '🚫 No Emoji'}
        </span>
      </p>

      {/* Status row */}
      {isDone && (
        <span className="text-emerald-400 text-xs font-semibold flex items-center gap-1.5 drop-shadow-[0_0_6px_rgba(16,185,129,0.4)] animate-in fade-in slide-in-from-left-2 duration-300">
          <span className="relative flex items-center justify-center">
            <CheckCircle2 size={14} className="text-emerald-400" />
            <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/20" style={{ animationDuration: '2s' }} />
          </span>
          Completed
        </span>
      )}

      {isCancelled && (
        <div className="flex items-center justify-between animate-in fade-in duration-200">
          <span className="text-orange-400 text-xs font-semibold flex items-center gap-1.5 drop-shadow-[0_0_4px_rgba(249,115,22,0.4)]">
            <Ban size={14} className="text-orange-400" /> Cancelled
          </span>
          <div className="flex items-center gap-1">
            {onRetry && (
              <Button
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onRetry(job.id); }}
                className="flex items-center gap-1 px-1.5 py-1 md:py-0.5 rounded-md text-[10px] font-medium transition-all bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border border-orange-500/20 h-auto"
                title="Retry this job"
              >
                <RefreshCw size={10} />
                Retry
              </Button>
            )}
            {onDismiss && (
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => { e.stopPropagation(); onDismiss(job.id); }}
                className="p-1.5 md:p-0.5 rounded-md text-muted-foreground hover:text-foreground transition-colors h-auto w-auto"
                title="Dismiss"
              >
                <X size={12} />
              </Button>
            )}
          </div>
        </div>
      )}

      {isFailed && (
        <div className="flex items-center justify-between animate-in fade-in duration-200">
          <span className="text-red-400 text-xs font-semibold flex items-center gap-1.5 drop-shadow-[0_0_4px_rgba(239,68,68,0.4)]">
            <XCircle size={14} className="text-red-400" /> {job.status}
          </span>
          <div className="flex items-center gap-1">
            {onRetry && (
              <Button
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onRetry(job.id); }}
                className="flex items-center gap-1 px-1.5 py-1 md:py-0.5 rounded-md text-[10px] font-medium transition-all bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border border-amber-500/20 h-auto"
                title="Retry this job"
              >
                <RefreshCw size={10} />
                Retry
              </Button>
            )}
            {onDismiss && (
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => { e.stopPropagation(); onDismiss(job.id); }}
                className="p-1.5 md:p-0.5 rounded-md text-muted-foreground hover:text-foreground transition-colors h-auto w-auto"
                title="Dismiss"
              >
                <X size={12} />
              </Button>
            )}
          </div>
        </div>
      )}

      {isQueued && (
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-xs font-medium flex items-center gap-1">
            <Clock size={14} /> Queued...
          </span>
          {onCancelQueued && (
            <Button
              variant="outline"
              onClick={(e) => { e.stopPropagation(); onCancelQueued(job.id); }}
              className="flex items-center gap-1 px-1.5 py-1 md:py-0.5 rounded-md text-[10px] font-medium transition-all bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20 h-auto"
              title="Cancel this queued job"
            >
              <Square size={10} />
              Cancel
            </Button>
          )}
        </div>
      )}

      {isRunning && (
        <div className="space-y-1.5 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex justify-between items-center text-[10px] font-medium">
            <span className="text-blue-400 truncate pr-2 flex items-center gap-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
              </span>
              <span className="drop-shadow-[0_0_2px_rgba(59,130,246,0.3)]">{job.status || 'Processing'}</span>
            </span>
            <span className="text-foreground/80 font-semibold tabular-nums">{p}%</span>
          </div>
          <MultiSegmentProgressBar progress={p} segments={progressSegments} isRunning={isRunning} />
        </div>
      )}
      {streamingScript?.isActive && streamingScript?.text && (
        <div className="mt-1.5 text-[10px] text-blue-300/70 font-mono leading-relaxed truncate bg-blue-500/5 border border-blue-500/10 rounded-md px-2 py-1">
          <span>{streamingScript.text.slice(-60)}</span>
          <span className="inline-block w-1.5 h-3 bg-blue-400 animate-pulse ml-0.5 align-middle rounded-sm" />
        </div>
      )}
    </div>
  )
}

export default JobCard
