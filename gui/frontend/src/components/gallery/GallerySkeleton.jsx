export default function GallerySkeleton({ count = 4 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      {[...Array(count)].map((_, i) => (
        <div
          key={i}
          className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm"
          style={{ animationDelay: `${i * 100}ms`, animationFillMode: 'both' }}
        >
          {/* Video area skeleton */}
          <div className="relative aspect-[9/16] bg-secondary/20 overflow-hidden">
            {/* Shimmer overlay */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.03] to-transparent bg-[length:200%_100%] animate-shimmer" />

            {/* Badge placeholders */}
            <div className="absolute top-3 left-3">
              <div className="h-4 w-12 rounded-full bg-secondary/40" />
            </div>
            <div className="absolute top-3 right-3">
              <div className="h-4 w-14 rounded-full bg-secondary/40" />
            </div>
          </div>

          {/* Body skeleton */}
          <div className="p-3.5 space-y-3">
            <div className="space-y-2">
              {/* Title placeholder */}
              <div className="h-3.5 bg-secondary/30 rounded w-3/4 overflow-hidden">
                <div className="h-full w-full bg-gradient-to-r from-transparent via-white/[0.03] to-transparent bg-[length:200%_100%] animate-shimmer" />
              </div>
              {/* Date placeholder */}
              <div className="h-2.5 bg-secondary/20 rounded w-1/2 overflow-hidden">
                <div className="h-full w-full bg-gradient-to-r from-transparent via-white/[0.03] to-transparent bg-[length:200%_100%] animate-shimmer" />
              </div>
            </div>

            {/* Divider placeholder */}
            <div className="h-px bg-border/20" />

            {/* Action buttons placeholder */}
            <div className="flex gap-1.5">
              <div className="flex-1 h-7 bg-secondary/20 rounded-lg" />
              <div className="flex-1 h-7 bg-secondary/20 rounded-lg" />
              <div className="flex-1 h-7 bg-secondary/20 rounded-lg" />
              <div className="flex-1 h-7 bg-secondary/20 rounded-lg" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
