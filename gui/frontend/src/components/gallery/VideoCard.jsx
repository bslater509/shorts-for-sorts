import { useState } from 'react'
import { Hash, Share2, Download, Trash2, Play } from 'lucide-react'
import LazyVideo from '@/components/LazyVideo'
import { Button } from "@/components/ui/button"

const formatSize = (bytes) => {
  if (!bytes) return '0 MB'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (timestamp) => {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString()
}

export default function VideoCard({ video, onCopyHashtags, onShare, onDelete }) {
  const [isPlaying, setIsPlaying] = useState(false);

  return (
    <div
      className="group relative bg-card border border-border/60 rounded-xl overflow-hidden shadow-lg shadow-black/15 hover:shadow-xl hover:shadow-primary/5 hover:border-primary/30 transition-all duration-300 flex flex-col hover:-translate-y-0.5"
      style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 500px' }}
    >
      {/* ── Video Preview ── */}
      <div className="relative aspect-[9/16] bg-black overflow-hidden">
        {/* Gradient overlay for depth */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent z-10 pointer-events-none" />

        {/* Top badges row */}
        <div className="absolute top-3 left-3 right-3 flex items-start justify-between z-20 pointer-events-none">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-black/60 backdrop-blur-sm text-white/90 border border-white/10 shadow-sm">
            <Play size={10} className="fill-white/90" />
            {video.duration ? `${video.duration.toFixed(1)}s` : 'Short'}
          </span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-black/60 backdrop-blur-sm text-white/80 border border-white/10 shadow-sm">
            {formatSize(video.size)}
          </span>
        </div>

        {/* Play button overlay on hover */}
        <div className={`absolute inset-0 z-10 flex items-center justify-center opacity-0 ${!isPlaying ? 'group-hover:opacity-100' : ''} transition-all duration-300 pointer-events-none`}>
          <div className="w-14 h-14 rounded-full bg-primary/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-primary/30 ring-1 ring-white/20 scale-90 group-hover:scale-100 transition-transform duration-300">
            <Play size={24} className="text-white ml-0.5 fill-white" />
          </div>
        </div>

        <LazyVideo 
          src={video.url} 
          poster={video.thumbnail} 
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        />
      </div>

      {/* ── Card Body ── */}
      <div className="p-3.5 flex flex-col gap-2.5 flex-1">
        {/* File Info */}
        <div className="space-y-0.5">
          <h3
            className="font-semibold text-sm leading-tight truncate text-foreground/85 group-hover:text-foreground transition-colors"
            title={video.filename}
          >
            {video.filename}
          </h3>
          <p className="text-[11px] text-muted-foreground/60">
            {formatDate(video.modified)}
          </p>
        </div>

        {/* Divider */}
        <div className="border-t border-border/20" />

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5 mt-auto">
          {video.hashtags && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onCopyHashtags(video)}
              className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-purple-500/5 text-purple-400/80 hover:bg-purple-500/20 hover:text-purple-300 transition-all"
              title="Copy hashtags and title"
            >
              <Hash size={13} />
              <span className="truncate">Tags</span>
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onShare(video)}
            className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-green-500/5 text-green-400/80 hover:bg-green-500/20 hover:text-green-300 transition-all"
            title="Share video"
          >
            <Share2 size={13} />
            <span className="truncate">Share</span>
          </Button>
          <a
            href={video.url}
            download={video.filename}
            className="flex-1 min-w-0 h-8 inline-flex items-center justify-center gap-1 px-2 rounded-lg text-[11px] font-medium bg-blue-500/5 text-blue-400/80 hover:bg-blue-500/20 hover:text-blue-300 transition-all"
            title="Download video"
          >
            <Download size={13} />
            <span className="truncate">Download</span>
          </a>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(video.filename)}
            className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-red-500/5 text-red-400/80 hover:bg-red-500/20 hover:text-red-300 transition-all"
            title="Delete video"
          >
            <Trash2 size={13} />
            <span className="truncate">Delete</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
