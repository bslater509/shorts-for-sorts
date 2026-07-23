import { Music, Upload, Trash2, Loader2, Play, Pause } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function MusicTab({ music, onUpload, onDelete, isUploading, playingAudio, onToggleAudio }) {
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
      <div className="relative group border-2 border-dashed border-purple-500/30 hover:border-purple-500/80 hover:bg-purple-500/5 rounded-2xl p-8 transition-all flex flex-col items-center justify-center text-center shrink-0">
        <input
          type="file"
          accept="audio/*"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          onChange={(e) => onUpload(e, 'music')}
          disabled={isUploading}
        />
        {isUploading ? (
          <Loader2 size={36} className="text-purple-500 mb-4 animate-spin" />
        ) : (
          <div className="w-16 h-16 rounded-full bg-purple-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300 shadow-lg">
            <Upload size={28} className="text-purple-400" />
          </div>
        )}
        <h3 className="text-lg font-bold text-foreground/90">Drop high-quality audio tracks</h3>
        <p className="text-sm text-muted-foreground mt-2 font-medium">MP3, WAV, FLAC supported</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {music.map(m => {
          const isPlaying = playingAudio === m.url;
          return (
            <div key={m.filename} className="group flex items-center gap-4 bg-white/5 border border-white/10 hover:border-purple-500/50 rounded-2xl p-4 transition-all hover:bg-purple-500/5 shadow-sm hover:shadow-purple-500/10">
              <button
                onClick={() => onToggleAudio(m.url)}
                className={cn("w-12 h-12 rounded-full flex items-center justify-center transition-all shadow-md shrink-0", isPlaying ? "bg-purple-500 text-white shadow-purple-500/40" : "bg-purple-500/20 text-purple-400 group-hover:bg-purple-500 group-hover:text-white")}
              >
                {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-1" />}
              </button>
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-sm truncate">{m.filename}</h4>
                <p className="text-xs text-muted-foreground mt-1 font-medium">{(m.size / (1024 * 1024)).toFixed(1)} MB</p>
              </div>
              <button
                onClick={() => onDelete(m.filename, 'music')}
                className="text-muted-foreground hover:text-red-400 transition-colors p-3 hover:bg-red-500/10 rounded-full"
              >
                <Trash2 size={18} />
              </button>
            </div>
          )
        })}
      </div>
      {music.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/60">
          <Music size={48} className="mb-4 opacity-50" />
          <p className="text-lg font-medium">No audio tracks uploaded yet</p>
        </div>
      )}
    </div>
  )
}
