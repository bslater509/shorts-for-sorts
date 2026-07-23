import { Upload, Trash2, Video, Loader2 } from 'lucide-react'

export default function VideosTab({ videos, onUpload, onDelete, isUploading }) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
      <div className="relative group border-2 border-dashed border-blue-500/30 hover:border-blue-500/80 hover:bg-blue-500/5 rounded-2xl p-8 transition-all flex flex-col items-center justify-center text-center shrink-0">
        <input
          type="file"
          accept="video/mp4,video/mov,video/webm"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          onChange={(e) => onUpload(e, 'video')}
          disabled={isUploading}
        />
        {isUploading ? (
          <Loader2 size={36} className="text-blue-500 mb-4 animate-spin" />
        ) : (
          <div className="w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300 shadow-lg">
            <Upload size={28} className="text-blue-400" />
          </div>
        )}
        <h3 className="text-lg font-bold text-foreground/90">Drop gorgeous 9:16 loops here</h3>
        <p className="text-sm text-muted-foreground mt-2 font-medium">MP4, MOV, WEBM supported</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-6">
        {videos.map(v => (
          <div key={v.filename} className="group relative bg-black/40 rounded-2xl border border-white/5 overflow-hidden aspect-[9/16] flex flex-col shadow-lg hover:shadow-blue-500/20 transition-all duration-300 hover:-translate-y-1 cursor-crosshair">
            <video
              src={v.url}
              className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-500"
              muted
              loop
              onMouseEnter={(e) => e.target.play().catch(() => { })}
              onMouseLeave={(e) => { e.target.pause(); e.target.currentTime = 0; }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none" />

            <div className="absolute bottom-0 inset-x-0 p-4 flex flex-col z-10 pointer-events-none">
              <p className="text-white text-xs font-semibold truncate drop-shadow-md mb-1">{v.filename}</p>
              <div className="flex items-center gap-2 text-[10px] text-white/70 font-medium">
                <span className="bg-white/20 px-2 py-0.5 rounded-full backdrop-blur-md">{(v.size / (1024 * 1024)).toFixed(1)} MB</span>
              </div>
            </div>

            <button
              onClick={() => onDelete(v.filename, 'video')}
              className="absolute top-3 right-3 bg-red-500/80 hover:bg-red-600 text-white p-2 rounded-xl opacity-0 group-hover:opacity-100 transition-all duration-300 backdrop-blur-md shadow-lg z-20 hover:scale-110"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
      {videos.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/60">
          <Video size={48} className="mb-4 opacity-50" />
          <p className="text-lg font-medium">No video loops uploaded yet</p>
        </div>
      )}
    </div>
  )
}
