import { useState } from 'react'
import { Hash, Share2, Download, Trash2, Play, Upload, Loader2 } from 'lucide-react'
import LazyVideo from '@/components/LazyVideo'
import RetryingImage from '@/components/RetryingImage'
import { Button } from "@/components/ui/button"

const formatSize = (bytes) => {
  if (!bytes) return '0 MB'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (timestamp) => {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString()
}

export default function VideoCard({ video, onCopyHashtags, onShare, onDelete, onTikTok, onPreview, tiktokUploading, tiktokProgress }) {
  const [isPlaying, setIsPlaying] = useState(false);

  return (
    <div
      className="group relative bg-card border border-border/60 rounded-xl overflow-hidden shadow-lg shadow-black/15 hover:shadow-xl hover:shadow-primary/5 hover:border-primary/30 transition-all duration-300 flex gap-3 p-3 sm:flex-col sm:gap-0 sm:p-0 hover:-translate-y-0.5"
      style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 200px' }}
    >
      {/* ── Video Preview ── */}
      <div className="relative aspect-[9/16] w-24 shrink-0 sm:w-auto bg-black overflow-hidden rounded-lg sm:rounded-none">
        {/* Gradient overlay for depth */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent z-10 pointer-events-none" />

        {/* TikTok upload status overlay */}
        {tiktokUploading && (
          <div className="absolute inset-0 z-[25] flex flex-col items-center justify-center bg-black/50 backdrop-blur-[2px]">
            <Loader2 size={28} className="text-rose-400 animate-spin mb-2" />
            <span className="text-[11px] font-medium text-white/90 text-center px-3 leading-tight">
              {tiktokProgress?.stage || 'Uploading…'}
            </span>
            {(tiktokProgress?.percent ?? 0) > 0 && (
              <span className="text-[10px] text-white/50 mt-1">
                {tiktokProgress.percent}%
              </span>
            )}
          </div>
        )}

        {/* TikTok upload progress bar */}
        {tiktokUploading && (
          <div className="absolute bottom-0 left-0 right-0 z-30">
            <div className="h-1 bg-white/10">
              <div
                className="h-full bg-rose-400 transition-all duration-700 ease-out"
                style={{ width: `${tiktokProgress?.percent ?? 0}%` }}
              />
            </div>
          </div>
        )}

        {/* Duration badge — always visible */}
        <div className="absolute top-1.5 left-1.5 sm:top-3 sm:left-3 z-20 pointer-events-none">
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] sm:text-[10px] font-semibold bg-black/60 backdrop-blur-sm text-white/90 border border-white/10 shadow-sm">
            <Play size={8} className="fill-white/90 sm:hidden" />
            <Play size={10} className="fill-white/90 hidden sm:inline" />
            {video.duration ? `${video.duration.toFixed(1)}s` : 'Short'}
          </span>
        </div>

        {/* Size badge — desktop only */}
        <div className="absolute top-3 right-3 z-20 pointer-events-none hidden sm:block">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-black/60 backdrop-blur-sm text-white/80 border border-white/10 shadow-sm">
            {formatSize(video.size)}
          </span>
        </div>

        {/* Mobile poster tap-target (opens preview modal) — hidden on sm+ */}
        <button
          className="absolute inset-0 z-20 flex items-center justify-center sm:hidden"
          onClick={() => onPreview?.(video)}
          aria-label="Preview video"
        >
          <div className="w-8 h-8 rounded-full bg-primary/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-primary/30 ring-1 ring-white/20">
            <Play size={14} className="text-white ml-0.5 fill-white" />
          </div>
        </button>

        {/* Desktop play button overlay on hover — hidden on mobile */}
        <div className={`absolute inset-0 z-10 hidden sm:flex items-center justify-center opacity-0 ${!isPlaying ? 'group-hover:opacity-100' : ''} transition-all duration-300 pointer-events-none`}>
          <div className="w-14 h-14 rounded-full bg-primary/80 backdrop-blur-sm flex items-center justify-center shadow-lg shadow-primary/30 ring-1 ring-white/20 scale-90 group-hover:scale-100 transition-transform duration-300">
            <Play size={24} className="text-white ml-0.5 fill-white" />
          </div>
        </div>

        {/* Desktop inline video — hidden on mobile */}
        <div className="hidden sm:block absolute inset-0">
          <LazyVideo
            src={video.url}
            poster={video.thumbnail}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => setIsPlaying(false)}
          />
        </div>

        {/* Mobile poster image — hidden on sm+ */}
        <div className="sm:hidden absolute inset-0 bg-black">
          {video.thumbnail ? (
            <RetryingImage
              src={video.thumbnail}
              alt=""
              className="absolute inset-0 w-full h-full object-cover opacity-80"
            />
          ) : (
            <div className="absolute inset-0 bg-secondary/30" />
          )}
        </div>
      </div>

      {/* ── Card Body ── */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5 py-0.5 sm:gap-2.5 sm:p-3.5">
        {/* File Info */}
        <div className="space-y-0.5">
          <h3
            className="font-semibold text-sm leading-tight truncate text-foreground/85 group-hover:text-foreground transition-colors"
            title={video.filename}
          >
            {video.filename}
          </h3>
          {/* Mobile: date · size on one line. Desktop: separate lines */}
          <p className="text-[11px] text-muted-foreground/60 sm:hidden">
            {formatDate(video.modified)}{video.size ? ` · ${formatSize(video.size)}` : ''}
          </p>
          <p className="text-[11px] text-muted-foreground/60 hidden sm:block">
            {formatDate(video.modified)}
          </p>
        </div>

        {/* Divider — desktop only */}
        <div className="border-t border-border/20 hidden sm:block" />

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5 mt-auto">
          {video.hashtags && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onCopyHashtags(video)}
              className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-purple-500/5 text-purple-400/80 hover:bg-purple-500/20 hover:text-purple-300 transition-all justify-center"
              title="Copy hashtags and title"
            >
              <Hash size={13} />
              <span className="truncate hidden sm:inline">Tags</span>
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onShare(video)}
            className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-green-500/5 text-green-400/80 hover:bg-green-500/20 hover:text-green-300 transition-all justify-center"
            title="Share video"
          >
            <Share2 size={13} />
            <span className="truncate hidden sm:inline">Share</span>
          </Button>
          <a
            href={video.url}
            download={video.filename}
            className="flex-1 min-w-0 h-8 inline-flex items-center justify-center gap-1 px-2 rounded-lg text-[11px] font-medium bg-blue-500/5 text-blue-400/80 hover:bg-blue-500/20 hover:text-blue-300 transition-all"
            title="Download video"
          >
            <Download size={13} />
            <span className="truncate hidden sm:inline">Download</span>
          </a>
          {onTikTok && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onTikTok(video)}
              disabled={tiktokUploading}
              className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-rose-500/5 text-rose-400/80 hover:bg-rose-500/20 hover:text-rose-300 transition-all justify-center"
              title="Upload video to TikTok"
            >
              {tiktokUploading ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <>
                  <Upload size={13} />
                  <span className="truncate hidden sm:inline">TikTok</span>
                </>
              )}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(video.filename)}
            className="flex-1 min-w-0 h-8 gap-1 px-2 rounded-lg text-[11px] font-medium bg-red-500/5 text-red-400/80 hover:bg-red-500/20 hover:text-red-300 transition-all justify-center"
            title="Delete video"
          >
            <Trash2 size={13} />
            <span className="truncate hidden sm:inline">Delete</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
