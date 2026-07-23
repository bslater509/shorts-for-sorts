import { useState, useEffect } from 'react'
import { Film, RefreshCw, Trash2, PlayCircle } from 'lucide-react'
import * as api from '@/lib/api'
import TikTokIcon from '@/components/gallery/TikTokIcon'
import GallerySkeleton from '@/components/gallery/GallerySkeleton'
import VideoCard from '@/components/gallery/VideoCard'
import TikTokUploadModal from '@/components/gallery/TikTokUploadModal'

export default function Gallery() {
  const [videos, setVideos] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [tiktokDescription, setTiktokDescription] = useState("")
  const [tiktokVisibility, setTiktokVisibility] = useState("Public")
  const [isUploading, setIsUploading] = useState(false)

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

  const openUploadModal = (video) => {
    setSelectedVideo(video)
    const videoTitle = video.title || video.filename.replace('.mp4', '')
    setTiktokDescription(`${videoTitle}\n${video.hashtags || ''}`)
    setTiktokVisibility("Public")
    setIsUploadModalOpen(true)
  }

  const handleUploadSubmit = async () => {
    if (!selectedVideo) return
    setIsUploading(true)
    try {
      await api.uploadTikTokVideo(selectedVideo.filename, tiktokDescription, tiktokVisibility)
      alert("TikTok upload started in background!")
      setIsUploadModalOpen(false)
    } catch (err) {
      alert(`Upload failed: ${err.message}`)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-7xl mx-auto flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)]">
      <header className="shrink-0 flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Film className="text-blue-500" />
            Rendered Videos Library
          </h1>
          <p className="text-muted-foreground mt-1">Browse, preview, and download completed vertical TikTok shorts</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleDeleteAll}
            disabled={isLoading || videos.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white border border-red-500/20 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <Trash2 size={16} />
            Delete All
          </button>
          <button
            onClick={loadGallery}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 border border-border rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            Refresh Library
          </button>
        </div>
      </header>

      <div className="flex-1 md:overflow-y-auto">
        {isLoading ? (
          <GallerySkeleton count={4} />
        ) : videos.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 pb-6">
            {videos.map((v) => (
              <VideoCard
                key={v.filename}
                video={v}
                onCopyHashtags={handleCopyHashtags}
                onShare={handleShare}
                onTikTokUpload={openUploadModal}
                onDelete={handleDelete}
              />
            ))}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground space-y-3 bg-card border border-dashed border-border rounded-xl p-12">
            <PlayCircle size={48} className="opacity-20 mb-2" />
            <p className="font-medium text-lg text-foreground">No compiled vertical shorts found.</p>
            <p className="text-sm max-w-sm">Head over to the Content Studio, generate a script, configure media, and compile your first video!</p>
          </div>
        )}
      </div>

      <TikTokUploadModal
        isOpen={isUploadModalOpen}
        video={selectedVideo}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSubmit}
        isUploading={isUploading}
        description={tiktokDescription}
        setDescription={setTiktokDescription}
        visibility={tiktokVisibility}
        setVisibility={setTiktokVisibility}
      />
    </div>
  )
}
