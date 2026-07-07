import { useState, useEffect } from 'react'
import { Film, RefreshCw, Trash2, Download, PlayCircle, Share2, Hash, Upload, X } from 'lucide-react'
import * as api from '@/lib/api'
import LazyVideo from '@/components/LazyVideo'

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
      const textToCopy = `${video.filename.replace('.mp4', '')}\n${video.hashtags || ''}`;
      try {
        await navigator.clipboard.writeText(textToCopy);
      } catch (err) {
        console.error("Failed to copy title and hashtags:", err);
      }

      const response = await fetch(video.url)
      const blob = await response.blob()
      const file = new File([blob], video.filename, { type: blob.type || 'video/mp4' })

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file]
        })
      } else {
        alert("Native file sharing is not supported on your browser. Downloading the file instead.")
        const blobUrl = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = blobUrl
        link.download = video.filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Error sharing video:", err)
        alert("An error occurred while sharing the video.")
      }
    }
  }

  const handleCopyHashtags = async (hashtags) => {
    if (!hashtags) return
    try {
      await navigator.clipboard.writeText(hashtags)
      alert("Hashtags copied to clipboard!")
    } catch (err) {
      console.error("Failed to copy hashtags:", err)
      alert("Failed to copy hashtags.")
    }
  }

  const openUploadModal = (video) => {
    setSelectedVideo(video)
    setTiktokDescription(`${video.filename.replace('.mp4', '')}\n${video.hashtags || ''}`)
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


  const formatSize = (bytes) => {
    if (!bytes) return '0 MB'
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    return new Date(timestamp * 1000).toLocaleString()
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
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-card border border-border rounded-xl overflow-hidden shadow-sm animate-pulse">
                <div className="aspect-[9/16] bg-secondary/50"></div>
                <div className="p-4 space-y-3">
                  <div className="h-4 bg-secondary rounded w-3/4"></div>
                  <div className="h-3 bg-secondary rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        ) : videos.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 pb-6">
            {videos.map((v) => (
              <div key={v.filename} className="group bg-card border border-border rounded-xl overflow-hidden shadow-sm hover:border-blue-500/30 transition-colors flex flex-col" style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 500px' }}>
                <div className="relative aspect-[9/16] bg-black">
                  <LazyVideo 
                    src={v.url}
                    poster={v.thumbnail}
                  />
                </div>
                
                <div className="p-4 flex flex-col gap-3 flex-1 bg-secondary/10">
                  <div>
                    <h3 className="font-semibold text-sm leading-tight truncate" title={v.filename}>
                      {v.filename}
                    </h3>
                    <div className="flex items-center justify-between mt-1 text-xs text-muted-foreground">
                      <span>{v.duration ? `${v.duration.toFixed(1)}s` : 'Short'} • {formatSize(v.size)}</span>
                      <span>{formatDate(v.modified)}</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 mt-auto pt-2">
                    {v.hashtags && (
                      <button 
                        onClick={() => handleCopyHashtags(v.hashtags)}
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-purple-500 hover:bg-purple-600 text-white rounded-md text-xs font-semibold transition-colors"
                        title="Copy Hashtags"
                      >
                        <Hash size={14} />
                      </button>
                    )}
                    <button 
                      onClick={() => handleShare(v)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-md text-xs font-semibold transition-colors"
                      title="Share Video"
                    >
                      <Share2 size={14} />
                    </button>
                    <button 
                      onClick={() => openUploadModal(v)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white rounded-md text-xs font-semibold transition-colors"
                      title="Upload to TikTok"
                    >
                      <Upload size={14} />
                    </button>
                    <a 
                      href={v.url} 
                      download={v.filename}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded-md text-xs font-semibold transition-colors"
                      title="Download Video"
                    >
                      <Download size={14} />
                    </a>
                    <button 
                      onClick={() => handleDelete(v.filename)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white rounded-md text-xs font-semibold transition-colors"
                      title="Delete Video"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
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

      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200 p-4">
          <div className="bg-card border border-border w-full max-w-md rounded-xl shadow-2xl overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-border bg-secondary/30">
              <h3 className="font-semibold flex items-center gap-2">
                <Upload size={18} className="text-pink-500" />
                Upload to TikTok
              </h3>
              <button onClick={() => setIsUploadModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Video File</label>
                <div className="text-sm text-muted-foreground bg-secondary/50 p-2 rounded truncate">
                  {selectedVideo?.filename}
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Description & Hashtags</label>
                <textarea 
                  value={tiktokDescription}
                  onChange={(e) => setTiktokDescription(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm min-h-[120px]"
                  placeholder="Enter description and tags..."
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Visibility</label>
                <select 
                  value={tiktokVisibility}
                  onChange={(e) => setTiktokVisibility(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm"
                >
                  <option value="Public">Public</option>
                  <option value="Friends">Friends Only</option>
                  <option value="Private">Private</option>
                </select>
              </div>
            </div>
            <div className="p-4 border-t border-border bg-secondary/30 flex justify-end gap-3">
              <button 
                onClick={() => setIsUploadModalOpen(false)}
                className="px-4 py-2 rounded-lg font-medium text-sm transition-colors hover:bg-secondary border border-border"
              >
                Cancel
              </button>
              <button 
                onClick={handleUploadSubmit}
                disabled={isUploading}
                className="px-6 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-medium text-sm shadow-md transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {isUploading ? "Starting..." : "Post to TikTok"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
