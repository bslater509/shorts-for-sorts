import { useState, useEffect } from 'react'
import { Video, Music, Globe, Upload, Trash2, Search, Download, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'

export default function MediaManager() {
  const [activeTab, setActiveTab] = useState('videos') // 'videos', 'music', 'pexels'
  const [videos, setVideos] = useState([])
  const [music, setMusic] = useState([])
  
  // Pexels State
  const [pexelsQuery, setPexelsQuery] = useState('')
  const [pexelsResults, setPexelsResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [downloadingId, setDownloadingId] = useState(null)

  const [isUploading, setIsUploading] = useState(false)

  const loadAssets = async () => {
    try {
      const [vids, mus] = await Promise.all([
        api.fetchVideos(),
        api.fetchMusic()
      ])
      setVideos(vids.videos || [])
      setMusic(mus.music || [])
    } catch (err) {
      console.error("Failed to load assets", err)
    }
  }

  useEffect(() => {
    loadAssets()
  }, [])

  const handleFileUpload = async (e, type) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setIsUploading(true)
    try {
      await api.uploadAsset(file, type)
      await loadAssets()
      alert('Upload successful!') // TODO: replace with proper toast
    } catch (err) {
      alert(`Upload failed: ${err.message}`)
    } finally {
      setIsUploading(false)
    }
  }

  const handleDelete = async (filename, type) => {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return
    try {
      if (type === 'video') await api.deleteVideo(filename)
      else await api.deleteMusic(filename)
      await loadAssets()
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  const handlePexelsSearch = async () => {
    if (!pexelsQuery.trim()) return
    setIsSearching(true)
    try {
      const data = await api.searchPexels(pexelsQuery)
      setPexelsResults(data.videos || [])
    } catch (err) {
      alert(`Search failed: ${err.message}`)
    } finally {
      setIsSearching(false)
    }
  }

  const handlePexelsDownload = async (video) => {
    setDownloadingId(video.id)
    try {
      const hdFile = video.video_files.find(f => f.height >= 1080 && f.width < f.height) 
                  || video.video_files[0]
                  
      await api.downloadPexelsVideo(hdFile.link, video.id, pexelsQuery, 'top')
      alert('Downloaded successfully to local library!')
      await loadAssets()
    } catch (err) {
      alert(`Download failed: ${err.message}`)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)] max-w-6xl mx-auto">
      <header className="shrink-0">
        <h1 className="text-3xl font-bold tracking-tight">Media Manager</h1>
        <p className="text-muted-foreground mt-1">Upload local video/audio tracks or search vertical videos on Pexels</p>
      </header>
      
      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border shrink-0 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        <button 
          onClick={() => setActiveTab('videos')}
          className={cn("px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2", activeTab === 'videos' ? "border-blue-500 text-blue-500" : "border-transparent text-muted-foreground hover:text-foreground")}
        >
          <Video size={16} /> Background Videos
        </button>
        <button 
          onClick={() => setActiveTab('music')}
          className={cn("px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2", activeTab === 'music' ? "border-blue-500 text-blue-500" : "border-transparent text-muted-foreground hover:text-foreground")}
        >
          <Music size={16} /> Background Music
        </button>
        <button 
          onClick={() => setActiveTab('pexels')}
          className={cn("px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2", activeTab === 'pexels' ? "border-emerald-500 text-emerald-500" : "border-transparent text-muted-foreground hover:text-foreground")}
        >
          <Globe size={16} /> Pexels Downloader
        </button>
      </div>

      <div className="flex-1 bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col">
        {/* VIDEOS TAB */}
        {activeTab === 'videos' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="relative group border-2 border-dashed border-border hover:border-blue-500/50 rounded-xl p-8 transition-colors flex flex-col items-center justify-center text-center bg-secondary/20 shrink-0">
              <input 
                type="file" 
                accept="video/mp4" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={(e) => handleFileUpload(e, 'video')}
                disabled={isUploading}
              />
              {isUploading ? (
                <Loader2 size={32} className="text-blue-500 mb-3 animate-spin" />
              ) : (
                <Upload size={32} className="text-blue-500 mb-3 group-hover:scale-110 transition-transform" />
              )}
              <h3 className="text-base font-semibold">Drag and drop background MP4 video loops</h3>
              <p className="text-sm text-muted-foreground mt-1">or click to browse local files</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {videos.map(v => (
                <div key={v.name} className="group relative bg-secondary rounded-xl border border-border overflow-hidden aspect-[9/16] flex flex-col">
                  {/* Since these are server paths, we need to construct a url. We can just use the backend static route if available, or just show the name. */}
                  <div className="flex-1 flex items-center justify-center bg-black/10 p-4 text-center break-all text-xs font-mono text-muted-foreground">
                    {v.name}
                  </div>
                  <button 
                    onClick={() => handleDelete(v.name, 'video')}
                    className="absolute top-2 right-2 bg-black/60 hover:bg-red-500 text-white p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-all backdrop-blur-sm"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {videos.length === 0 && <p className="col-span-full text-center text-muted-foreground py-8">No videos uploaded yet.</p>}
            </div>
          </div>
        )}

        {/* MUSIC TAB */}
        {activeTab === 'music' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="relative group border-2 border-dashed border-border hover:border-emerald-500/50 rounded-xl p-8 transition-colors flex flex-col items-center justify-center text-center bg-secondary/20 shrink-0">
              <input 
                type="file" 
                accept="audio/*" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={(e) => handleFileUpload(e, 'music')}
                disabled={isUploading}
              />
              {isUploading ? (
                <Loader2 size={32} className="text-emerald-500 mb-3 animate-spin" />
              ) : (
                <Upload size={32} className="text-emerald-500 mb-3 group-hover:scale-110 transition-transform" />
              )}
              <h3 className="text-base font-semibold">Drag and drop background MP3 / WAV tracks</h3>
              <p className="text-sm text-muted-foreground mt-1">or click to browse local files</p>
            </div>

            <div className="grid gap-3">
              {music.map(m => (
                <div key={m.name} className="group flex items-center justify-between bg-secondary/50 border border-border rounded-lg p-4 transition-colors hover:bg-secondary">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-md bg-emerald-500/10 flex items-center justify-center">
                      <Music size={20} className="text-emerald-500" />
                    </div>
                    <span className="font-medium text-sm">{m.name}</span>
                  </div>
                  <button 
                    onClick={() => handleDelete(m.name, 'music')}
                    className="text-muted-foreground hover:text-red-500 transition-colors p-2"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
              {music.length === 0 && <p className="text-center text-muted-foreground py-8">No audio tracks uploaded yet.</p>}
            </div>
          </div>
        )}

        {/* PEXELS TAB */}
        {activeTab === 'pexels' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="flex gap-3 shrink-0">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
                <input 
                  type="text" 
                  placeholder="e.g. 'satisfying slime', 'cyberpunk city aerial'"
                  className="w-full bg-background border border-border rounded-lg pl-10 pr-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 shadow-sm"
                  value={pexelsQuery}
                  onChange={e => setPexelsQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handlePexelsSearch()}
                />
              </div>
              <button 
                onClick={handlePexelsSearch}
                disabled={isSearching || !pexelsQuery.trim()}
                className="px-6 py-2 rounded-lg font-medium text-sm transition-all bg-emerald-500 hover:bg-emerald-600 text-white shadow-md disabled:opacity-50 flex items-center gap-2"
              >
                {isSearching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                Search
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {pexelsResults.map(video => {
                const isDownloading = downloadingId === video.id
                return (
                  <div key={video.id} className="group relative bg-black/20 rounded-xl border border-border overflow-hidden aspect-[9/16] flex flex-col">
                    <img src={video.image} alt={video.url} className="absolute inset-0 w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-3">
                      <p className="text-white text-xs font-medium truncate mb-2">{video.user?.name || 'Unknown'}</p>
                      <button 
                        onClick={() => handlePexelsDownload(video)}
                        disabled={isDownloading}
                        className="w-full py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded text-xs font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                      >
                        {isDownloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                        Download
                      </button>
                    </div>
                  </div>
                )
              })}
              {pexelsResults.length === 0 && !isSearching && (
                <p className="col-span-full text-center text-muted-foreground py-12">Enter a visual concept above to search Pexels videos.</p>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
