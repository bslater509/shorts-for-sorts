export default function GallerySkeleton({ count = 4 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      {[...Array(count)].map((_, i) => (
        <div key={i} className="bg-card border border-border rounded-xl overflow-hidden shadow-sm animate-pulse">
          <div className="aspect-[9/16] bg-secondary/50"></div>
          <div className="p-4 space-y-3">
            <div className="h-4 bg-secondary rounded w-3/4"></div>
            <div className="h-3 bg-secondary rounded w-1/2"></div>
          </div>
        </div>
      ))}
    </div>
  )
}
