import { Search, Download, Loader2, Globe } from 'lucide-react'

export default function PexelsTab({
  pexelsQuery,
  setPexelsQuery,
  pexelsResults,
  isSearching,
  downloadingId,
  onSearch,
  onDownload,
}) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
      <div className="flex gap-4 shrink-0 bg-white/5 p-2 rounded-2xl border border-white/10 shadow-inner">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-emerald-500/70" size={20} />
          <input
            type="text"
            placeholder="Search premium stock footage (e.g. 'cyberpunk neon city')"
            className="w-full bg-transparent border-none pl-12 pr-4 py-3 text-sm font-medium focus:outline-none focus:ring-0 text-foreground placeholder:text-muted-foreground"
            value={pexelsQuery}
            onChange={e => setPexelsQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSearch()}
          />
        </div>
        <button
          onClick={onSearch}
          disabled={isSearching || !pexelsQuery.trim()}
          className="px-8 py-3 rounded-xl font-bold text-sm transition-all bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 disabled:opacity-50 flex items-center gap-2"
        >
          {isSearching ? <Loader2 size={18} className="animate-spin" /> : null}
          Search
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-6">
        {pexelsResults.map(video => {
          const isDownloading = downloadingId === video.id
          return (
            <div key={video.id} className="group relative bg-black/40 rounded-2xl border border-white/5 overflow-hidden aspect-[9/16] flex flex-col shadow-lg hover:-translate-y-1 transition-all duration-300">
              <img src={video.thumbnail} alt="Pexels Thumbnail" className="absolute inset-0 w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-105 transition-all duration-700" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none flex flex-col justify-end p-4">
                <p className="text-white text-xs font-bold truncate mb-3 drop-shadow-md">by {video.user?.name || 'Unknown'}</p>
                <button
                  onClick={() => onDownload(video)}
                  disabled={isDownloading}
                  className="w-full py-2.5 bg-white/20 hover:bg-emerald-500 backdrop-blur-md text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 pointer-events-auto border border-white/10"
                >
                  {isDownloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                  {isDownloading ? 'Saving...' : 'Get Asset'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
      {pexelsResults.length === 0 && !isSearching && (
        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/50">
          <Globe size={48} className="mb-4 opacity-30" />
          <p className="text-lg font-medium">Search the globe for stunning visuals</p>
        </div>
      )}
    </div>
  )
}
