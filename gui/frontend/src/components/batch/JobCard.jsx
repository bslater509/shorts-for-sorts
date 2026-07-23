import { CheckCircle2, XCircle, Clock } from 'lucide-react'
import MultiSegmentProgressBar from './MultiSegmentProgressBar'

const JobCard = ({ job, onClick, progressSegments }) => {
  const isDone = job.status === 'Done'
  const isFailed = job.failed || job.status?.startsWith('Failed')
  const isQueued = job.status === 'Queued'
  const isRunning = !isDone && !isFailed && !isQueued
  const p = job.progress || 0

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick() }}
      className="bg-background border border-border/50 rounded-xl p-4 flex flex-col gap-3 shadow-sm hover:border-blue-500/30 hover:shadow-[0_4px_20px_-4px_rgba(59,130,246,0.1)] transition-all duration-300 relative overflow-hidden backdrop-blur-sm cursor-pointer"
    >
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
            <MultiSegmentProgressBar progress={p} segments={progressSegments} />
          </div>
        )}
      </div>
    </div>
  )
}

export default JobCard
