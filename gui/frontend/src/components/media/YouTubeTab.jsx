import { Search, Download, Loader2, PlaySquare } from 'lucide-react'

export default function YouTubeTab({
  youtubeQuery,
  setYoutubeQuery,
  youtubeResults,
  youtubeUrl,
  setYoutubeUrl,
  youtubeDownscale,
  setYoutubeDownscale,
  isYoutubeSearching,
  isYoutubeDownloading,
  onSearch,
  onDownload,
}) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
      {/* Search Bar */}
      <div className="flex gap-4 shrink-0 bg-white/5 p-2 rounded-2xl border border-white/10 shadow-inner flex-col sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-red-500/70" size={20} />
          <input
            type="text"
            placeholder="Search YouTube (e.g. 'satisfying kinetic sand loop') or paste URL below..."
            className="w-full bg-transparent border-none pl-12 pr-4 py-3 text-sm font-medium focus:outline-none focus:ring-0 text-foreground placeholder:text-muted-foreground"
            value={youtubeQuery}
            onChange={e => setYoutubeQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSearch()}
          />
        </div>
        <button
          onClick={onSearch}
          disabled={isYoutubeSearching || !youtubeQuery.trim()}
          className="px-8 py-3 rounded-xl font-bold text-sm transition-all bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20 hover:shadow-red-500/40 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isYoutubeSearching ? <Loader2 size={18} className="animate-spin" /> : null}
          Search
        </button>
      </div>

      {/* Direct URL Download Option */}
      <div className="flex flex-col sm:flex-row items-center gap-4 p-4 rounded-2xl bg-white/5 border border-white/10">
        <input
          type="text"
          placeholder="Or paste direct YouTube URL..."
          className="flex-1 w-full bg-black/20 border border-white/5 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-red-500/50"
          value={youtubeUrl}
          onChange={e => setYoutubeUrl(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm font-medium text-muted-foreground cursor-pointer shrink-0">
          <input type="checkbox" checked={youtubeDownscale} onChange={e => setYoutubeDownscale(e.target.checked)} className="rounded text-red-500 focus:ring-red-500/50 bg-black/20 border-white/10" />
          Downscale 720p
        </label>
        <button
          onClick={() => onDownload()}
          disabled={isYoutubeDownloading || !youtubeUrl.trim()}
          className="w-full sm:w-auto px-6 py-2.5 rounded-xl font-bold text-sm transition-all bg-white/10 hover:bg-red-500 text-white disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isYoutubeDownloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          Download URL
        </button>
      </div>

      {/* Search Results Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-6">
        {youtubeResults.map(video => (
          <div key={video.id} className="group relative bg-black/40 rounded-2xl border border-white/5 overflow-hidden flex flex-col shadow-lg hover:-translate-y-1 transition-all duration-300">
            <div className="relative aspect-video overflow-hidden">
              {video.thumbnail ? (
                <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 opacity-90 group-hover:opacity-100" />
              ) : (
                <div className="w-full h-full bg-zinc-900 flex items-center justify-center">
                  <PlaySquare size={32} className="text-zinc-700" />
                </div>
              )}
              <div className="absolute bottom-2 right-2 bg-black/80 backdrop-blur-md text-white text-[10px] font-bold px-2 py-1 rounded-md">
                {video.duration_str || 'Live'}
              </div>
            </div>
            <div className="p-4 flex flex-col flex-1">
              <h4 className="text-sm font-bold leading-tight mb-2 line-clamp-2" title={video.title}>{video.title}</h4>
              <p className="text-xs text-muted-foreground font-medium mb-4">{video.uploader}</p>

              <div className="mt-auto">
                <button
                  onClick={() => onDownload(video.url)}
                  disabled={isYoutubeDownloading}
                  className="w-full py-2.5 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 border border-red-500/20 hover:border-red-500"
                >
                  <Download size={14} /> Download
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {youtubeResults.length === 0 && !isYoutubeSearching && (
        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/40 pb-12">
          <PlaySquare size={56} className="mb-4 opacity-20" />
          <p className="text-lg font-medium">Search for YouTube background loops</p>
        </div>
      )}
    </div>
  )
}
