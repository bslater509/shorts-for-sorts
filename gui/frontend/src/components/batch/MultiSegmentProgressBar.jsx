const DEFAULT_SEGMENTS = []

const SEGMENT_GRADIENTS = [
  { from: 'from-pink-500 to-rose-500', shadow: 'rgba(236,72,153,0.6)' },
  { from: 'from-rose-500 to-amber-500', shadow: 'rgba(245,158,11,0.6)' },
  { from: 'from-amber-500 to-emerald-500', shadow: 'rgba(16,185,129,0.6)' },
  { from: 'from-emerald-500 to-cyan-500', shadow: 'rgba(6,182,212,0.6)' },
]

const MultiSegmentProgressBar = ({ progress, segments, isRunning = false }) => {
  const segs = segments && segments.length > 0 ? segments : DEFAULT_SEGMENTS

  if (segs.length === 0) {
    return (
      <div className="w-full h-2 rounded-full overflow-hidden bg-background/50 border border-border/50 relative">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-500 ease-out rounded-full relative overflow-hidden"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        >
          {isRunning && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer-fast" style={{ backgroundSize: '200% 100%' }} />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full flex gap-0.5 h-2 rounded-full overflow-hidden bg-background/50 border border-border/50 p-[1px]">
      {segs.map((seg, i) => {
        const flex = seg.end - seg.start
        const fill = Math.min(100, Math.max(0, ((progress - seg.start) / (seg.end - seg.start)) * 100))
        const gradient = SEGMENT_GRADIENTS[i % SEGMENT_GRADIENTS.length]
        return (
          <div key={seg.name || i} className="h-full bg-secondary/30 rounded-sm" style={{ flex }}>
            <div
              className={`h-full bg-gradient-to-r ${gradient.from} transition-all duration-500 ease-out rounded-sm relative overflow-hidden`}
              style={{ width: `${fill}%`, boxShadow: `0 0 6px ${gradient.shadow}` }}
            >
              {isRunning && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent animate-shimmer-fast" style={{ backgroundSize: '200% 100%' }} />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default MultiSegmentProgressBar
