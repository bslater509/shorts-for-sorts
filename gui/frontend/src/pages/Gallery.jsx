import { useState, useEffect } from 'react'
import { Film, RefreshCw, Trash2, Clapperboard, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as api from '@/lib/api'
import { postToTikTok, getTikTokStatus } from '@/lib/api'
import GallerySkeleton from '@/components/gallery/GallerySkeleton'
import VideoCard from '@/components/gallery/VideoCard'
import VideoPreviewModal from '@/components/gallery/VideoPreviewModal'

export default function Gallery() {
  const [videos, setVideos] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [tiktokUploading, setTiktokUploading] = useState(null)
  const [tiktokResult, setTiktokResult] = useState(null)
  const [tiktokProgress, setTiktokProgress] = useState({ stage: '', percent: 0 })
  const [previewVideo, setPreviewVideo] = useState(null)

  const loadGallery = async () => {
    setIsLoading(true)
    try {
      const data = await api.fetchGallery()
      setVideos(data || [])
    } catch (err) {
      console.error("Failed to load gallery", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadGallery()
  }, [])

  const handleDelete = async (filename) => {
    if (!confirm(`Are you sure you want to delete this completed video: "${filename}"?`)) return
    try {
      await api.deleteGalleryVideo(filename)
      await loadGallery()
    } catch (err) {
      alert(`Failed to delete video: ${err.message}`)
    }
  }

  const handleDeleteAll = async () => {
    if (videos.length === 0) return
    if (!confirm(`Are you sure you want to delete ALL generated videos? This cannot be undone.`)) return
    try {
      await api.deleteAllGalleryVideos()
      await loadGallery()
    } catch (err) {
      alert(`Failed to delete all videos: ${err.message}`)
    }
  }

  const handleShare = async (video) => {
    try {
      const videoTitle = video.title || video.filename.replace('.mp4', '')
      const textToCopy = `${videoTitle}\n${video.hashtags || ''}`;

      const response = await fetch(video.url)
      const blob = await response.blob()
      const file = new File([blob], video.filename, { type: blob.type || 'video/mp4' })
      const shareData = {
        files: [file]
      };

      const fallbackDownload = (fileBlob) => {
        const blobUrl = URL.createObjectURL(fileBlob)
        const link = document.createElement('a')
        link.href = blobUrl
        link.download = video.filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
      }

      if (navigator.canShare && navigator.canShare(shareData)) {
        try {
          await navigator.share(shareData)
        } catch (shareErr) {
          if (shareErr.name === 'NotAllowedError') {
            console.warn("Share API blocked due to lost user activation, falling back to download.");
            fallbackDownload(blob);
          } else {
            throw shareErr;
          }
        }
      } else {
        alert("Native file sharing is not supported on your browser. Downloading the file instead.")
        fallbackDownload(blob);
      }

      try {
        await navigator.clipboard.writeText(textToCopy);
      } catch (err) {
        console.error("Failed to copy title and hashtags:", err);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Error sharing video:", err)
        alert("An error occurred while sharing the video.")
      }
    }
  }

  const handleCopyHashtags = async (video) => {
    if (!video.hashtags) return
    const videoTitle = video.title || video.filename.replace('.mp4', '')
    try {
      await navigator.clipboard.writeText(`${videoTitle}\n${video.hashtags}`)
      alert("Title and hashtags copied to clipboard!")
    } catch (err) {
      console.error("Failed to copy:", err)
      alert("Failed to copy title and hashtags.")
    }
  }

  const handleTikTok = async (video) => {
    if (tiktokUploading) return
    setTiktokUploading(video.filename)
    setTiktokResult(null)
    setTiktokProgress({ stage: '', percent: 0 })
    try {
      await postToTikTok(video.filename)
      // Upload started in background; poll /api/tiktok/status every 3s until not uploading
      const poll = setInterval(async () => {
        try {
          const s = await getTikTokStatus()
          if (s.state === 'uploading') {
            setTiktokProgress({ stage: s.stage || '', percent: s.percent ?? 0 })
          } else {
            clearInterval(poll)
            setTiktokUploading(null)
            setTiktokProgress({ stage: '', percent: 0 })
            const succeeded = s.state === 'done'
            if (succeeded) {
              try { await api.deleteGalleryVideo(video.filename) } catch { /* ignore */ }
              await loadGallery()
            }
            setTiktokResult({ filename: video.filename, success: succeeded, error: s.error })
            setTimeout(() => setTiktokResult(null), 6000)
          }
        } catch { clearInterval(poll); setTiktokUploading(null); setTiktokProgress({ stage: '', percent: 0 }) }
      }, 3000)
    } catch (err) {
      setTiktokUploading(null)
      setTiktokProgress({ stage: '', percent: 0 })
      setTiktokResult({ filename: video.filename, success: false, error: err.message })
      setTimeout(() => setTiktokResult(null), 6000)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-7xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)]">
      {/* ── Header ── */}
      <header className="shrink-0 flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-accent/10 flex items-center justify-center ring-1 ring-primary/15 shadow-sm">
            <Film className="text-primary/80" size={20} />
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight">
              Rendered Videos
            </h1>
            <p className="text-sm text-muted-foreground/70 mt-0.5">
              Browse, preview, and download completed vertical shorts
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            onClick={handleDeleteAll}
            disabled={isLoading || videos.length === 0}
            variant="outline"
            className="h-8 gap-1.5 px-3 rounded-lg text-xs border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/30 disabled:opacity-40 transition-all"
          >
            <Trash2 size={13} />
            <span>Delete All</span>
          </Button>
          <Button
            onClick={loadGallery}
            disabled={isLoading}
            variant="outline"
            className="h-8 gap-1.5 px-3 rounded-lg text-xs border-border/50 bg-transparent text-muted-foreground hover:bg-secondary/30 hover:text-foreground transition-all"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </Button>
        </div>
      </header>

      {/* ── TikTok Upload Result Banner ── */}
      {tiktokResult && (
        <div
          className={`shrink-0 flex items-center gap-2.5 px-4 py-3 rounded-xl border animate-in fade-in slide-in-from-top-2 duration-300 ${
            tiktokResult.success
              ? "bg-green-500/10 border-green-500/30 text-green-400"
              : "bg-red-500/10 border-red-500/30 text-red-400"
          }`}
        >
          {tiktokResult.success ? (
            <CheckCircle2 size={16} className="shrink-0" />
          ) : (
            <XCircle size={16} className="shrink-0" />
          )}
          <span className="text-sm font-medium">
            {tiktokResult.success
              ? `Posted to TikTok: ${tiktokResult.filename}`
              : `TikTok upload failed: ${tiktokResult.error}`}
          </span>
        </div>
      )}

      {/* ── Content ── */}
      <div className="flex-1 md:overflow-y-auto overscroll-contain touch-pan-y">
        {isLoading ? (
          <GallerySkeleton count={4} />
        ) : videos.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-6 pb-6">
            {videos.map((v, i) => (
              <div
                key={v.filename}
                className="animate-in fade-in slide-in-from-bottom-3 duration-500"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <VideoCard
                  video={v}
                  onCopyHashtags={handleCopyHashtags}
                  onShare={handleShare}
                  onDelete={handleDelete}
                  onTikTok={handleTikTok}
                  onPreview={setPreviewVideo}
                  tiktokUploading={tiktokUploading === v.filename}
                  tiktokProgress={tiktokUploading === v.filename ? tiktokProgress : null}
                />
              </div>
            ))}
          </div>
        ) : (
          /* ── Empty State ── */
          <div className="h-full flex flex-col items-center justify-center text-center py-16 md:py-24">
            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary/10 to-accent/5 flex items-center justify-center ring-1 ring-primary/10 mb-6 shadow-lg shadow-primary/5">
              <Clapperboard size={40} className="text-primary/40" />
            </div>
            <h2 className="text-xl font-semibold text-foreground mb-2">
              No videos yet
            </h2>
            <p className="text-sm text-muted-foreground/70 max-w-md leading-relaxed">
              Head over to the <span className="text-primary/80 font-medium">Content Studio</span>, generate a script,
              configure your media, and compile your first vertical short.
            </p>
            <div className="mt-8 flex items-center gap-2 text-[11px] text-muted-foreground/40 uppercase tracking-widest font-medium">
              <span className="w-8 h-px bg-border/30" />
              <span>Your creations will appear here</span>
              <span className="w-8 h-px bg-border/30" />
            </div>
          </div>
        )}
      </div>

      {previewVideo && (
        <VideoPreviewModal video={previewVideo} onClose={() => setPreviewVideo(null)} />
      )}
    </div>
  )
}
