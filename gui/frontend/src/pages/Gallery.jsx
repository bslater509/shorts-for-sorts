import { useState, useEffect } from 'react'
import { Film, RefreshCw, Trash2, Download, PlayCircle, Share2 } from 'lucide-react'
import * as api from '@/lib/api'

export default function Gallery() {
  const [videos, setVideos] = useState([])
  const [isLoading, setIsLoading] = useState(true)

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

  const handleShare = async (video) => {
    try {
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
        
        <button 
          onClick={loadGallery}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 border border-border rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
          Refresh Library
        </button>
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
              <div key={v.filename} className="group bg-card border border-border rounded-xl overflow-hidden shadow-sm hover:border-blue-500/30 transition-colors flex flex-col">
                <div className="relative aspect-[9/16] bg-black">
                  <video 
                    className="absolute inset-0 w-full h-full object-contain"
                    src={v.url} 
                    controls 
                    preload="metadata"
                    playsInline
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
                    <button 
                      onClick={() => handleShare(v)}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-md text-xs font-semibold transition-colors"
                      title="Share Video"
                    >
                      <Share2 size={14} /> Share
                    </button>
                    <a 
                      href={v.url} 
                      download={v.filename}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded-md text-xs font-semibold transition-colors"
                    >
                      <Download size={14} /> Download
                    </a>
                    <button 
                      onClick={() => handleDelete(v.filename)}
                      className="px-3 py-1.5 text-red-500 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 rounded-md transition-colors"
                      title="Delete Video"
                    >
                      <Trash2 size={16} />
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
    </div>
  )
}
