import { CheckCircle2, XCircle, Clock, RefreshCw, Ban, X, Square } from 'lucide-react'
import MultiSegmentProgressBar from './MultiSegmentProgressBar'
import { Button } from "@/components/ui/button"

const JobCard = ({ job, onClick, progressSegments, onRetry, onDismiss, onCancelQueued }) => {
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
      className="bg-background border border-border/50 rounded-xl p-3 flex flex-col gap-2 shadow-sm hover:border-blue-500/30 hover:shadow-[0_4px_20px_-4px_rgba(59,130,246,0.1)] transition-all duration-300 relative overflow-hidden backdrop-blur-sm cursor-pointer"
    >
      {isRunning && <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 via-transparent to-transparent pointer-events-none" />}

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
        <span className="text-emerald-500 text-xs font-semibold flex items-center gap-1 drop-shadow-[0_0_4px_rgba(16,185,129,0.5)]">
          <CheckCircle2 size={14} /> Completed
        </span>
      )}

      {isCancelled && (
        <div className="flex items-center justify-between">
          <span className="text-orange-400 text-xs font-semibold flex items-center gap-1 drop-shadow-[0_0_4px_rgba(249,115,22,0.5)]">
            <Ban size={14} /> Cancelled
          </span>
          <div className="flex items-center gap-1">
            {onRetry && (
              <Button
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onRetry(job.id); }}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium transition-all bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border border-orange-500/20 h-auto"
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
                className="p-0.5 rounded-md text-muted-foreground hover:text-foreground transition-colors h-auto w-auto"
                title="Dismiss"
              >
                <X size={12} />
              </Button>
            )}
          </div>
        </div>
      )}

      {isFailed && (
        <div className="flex items-center justify-between">
          <span className="text-red-500 text-xs font-semibold flex items-center gap-1 drop-shadow-[0_0_4px_rgba(239,68,68,0.5)]">
            <XCircle size={14} /> {job.status}
          </span>
          <div className="flex items-center gap-1">
            {onRetry && (
              <Button
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onRetry(job.id); }}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium transition-all bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border border-amber-500/20 h-auto"
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
                className="p-0.5 rounded-md text-muted-foreground hover:text-foreground transition-colors h-auto w-auto"
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
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium transition-all bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20 h-auto"
              title="Cancel this queued job"
            >
              <Square size={10} />
              Cancel
            </Button>
          )}
        </div>
      )}

      {isRunning && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-medium">
            <span className="text-blue-500 truncate pr-2 drop-shadow-[0_0_2px_rgba(59,130,246,0.3)]">{job.status}</span>
            <span className="text-foreground shrink-0">{p}%</span>
          </div>
          <MultiSegmentProgressBar progress={p} segments={progressSegments} />
        </div>
      )}
    </div>
  )
}

export default JobCard
