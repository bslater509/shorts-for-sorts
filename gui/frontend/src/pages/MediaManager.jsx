import { useState, useEffect, useRef } from 'react'
import { Video, Music, Globe, Upload, Trash2, Search, Download, Loader2, PlaySquare, Play, Pause } from 'lucide-react'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'

export default function MediaManager() {
  const [activeTab, setActiveTab] = useState('videos') // 'videos', 'music', 'pexels', 'youtube'
  const [videos, setVideos] = useState([])
  const [music, setMusic] = useState([])
  
  // Pexels State
  const [pexelsQuery, setPexelsQuery] = useState('')
  const [pexelsResults, setPexelsResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [downloadingId, setDownloadingId] = useState(null)

  // YouTube State
  const [youtubeQuery, setYoutubeQuery] = useState('')
  const [youtubeResults, setYoutubeResults] = useState([])
  const [isYoutubeSearching, setIsYoutubeSearching] = useState(false)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [youtubeDownscale, setYoutubeDownscale] = useState(true)
  const [isYoutubeDownloading, setIsYoutubeDownloading] = useState(false)

  const [isUploading, setIsUploading] = useState(false)
  
  // Audio state
  const [playingAudio, setPlayingAudio] = useState(null)
  const audioRef = useRef(null)

  const loadAssets = async () => {
    try {
      const [vids, mus] = await Promise.all([
        api.fetchVideos(),
        api.fetchMusic()
      ])
      setVideos(Array.isArray(vids) ? vids : (vids.videos || []))
      setMusic(Array.isArray(mus) ? mus : (mus.music || []))
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

  const handleYoutubeSearch = async () => {
    if (!youtubeQuery.trim()) return
    setIsYoutubeSearching(true)
    try {
      const data = await api.searchYoutube(youtubeQuery, 12)
      setYoutubeResults(data.videos || [])
    } catch (err) {
      alert(`YouTube search failed: ${err.message}`)
    } finally {
      setIsYoutubeSearching(false)
    }
  }

  const handleYoutubeDownload = async (urlToDownload) => {
    const targetUrl = urlToDownload || youtubeUrl
    if (!targetUrl.trim()) return
    
    setIsYoutubeDownloading(true)
    try {
      await api.downloadYoutubeVideo(targetUrl, youtubeDownscale)
      alert('YouTube download started! It will appear in your library when finished.')
      if (!urlToDownload) setYoutubeUrl('')
    } catch (err) {
      alert(`YouTube download failed: ${err.message}`)
    } finally {
      setIsYoutubeDownloading(false)
    }
  }

  const toggleAudio = (url) => {
    if (playingAudio === url) {
      audioRef.current?.pause()
      setPlayingAudio(null)
    } else {
      setPlayingAudio(url)
      if (audioRef.current) {
        audioRef.current.src = url
        audioRef.current.play().catch(e => console.error("Playback failed", e))
      }
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)] max-w-7xl mx-auto">
      <header className="shrink-0 pt-4">
        <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-600 bg-clip-text text-transparent drop-shadow-sm">Media Manager</h1>
        <p className="text-muted-foreground mt-2 text-lg">Curate your assets, search the web, and build your premium library.</p>
      </header>
      
      {/* Audio Element for preview */}
      <audio ref={audioRef} onEnded={() => setPlayingAudio(null)} className="hidden" />
      
      {/* Tabs */}
      <div className="flex items-center gap-4 border-b border-border/50 shrink-0 overflow-x-auto pb-2 [&::-webkit-scrollbar]:hidden">
        {[
          { id: 'videos', icon: Video, label: 'Local Videos', color: 'blue' },
          { id: 'music', icon: Music, label: 'Local Music', color: 'purple' },
          { id: 'pexels', icon: Globe, label: 'Pexels Stock', color: 'emerald' },
          { id: 'youtube', icon: PlaySquare, label: 'YouTube Fetch', color: 'red' },
        ].map(tab => (
          <button 
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-5 py-3 text-sm font-semibold rounded-t-xl transition-all flex items-center gap-2",
              activeTab === tab.id 
                ? `bg-${tab.color}-500/10 text-${tab.color}-500 border-b-2 border-${tab.color}-500 shadow-[inset_0_-2px_10px_rgba(0,0,0,0.05)]` 
                : "border-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground"
            )}
          >
            <tab.icon size={18} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 bg-card/40 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* VIDEOS TAB */}
        {activeTab === 'videos' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="relative group border-2 border-dashed border-blue-500/30 hover:border-blue-500/80 hover:bg-blue-500/5 rounded-2xl p-8 transition-all flex flex-col items-center justify-center text-center shrink-0">
              <input 
                type="file" 
                accept="video/mp4,video/mov,video/webm" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={(e) => handleFileUpload(e, 'video')}
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
                    onMouseEnter={(e) => e.target.play().catch(()=>{})}
                    onMouseLeave={(e) => { e.target.pause(); e.target.currentTime = 0; }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none" />
                  
                  <div className="absolute bottom-0 inset-x-0 p-4 flex flex-col z-10 pointer-events-none">
                    <p className="text-white text-xs font-semibold truncate drop-shadow-md mb-1">{v.filename}</p>
                    <div className="flex items-center gap-2 text-[10px] text-white/70 font-medium">
                      <span className="bg-white/20 px-2 py-0.5 rounded-full backdrop-blur-md">{(v.size / (1024*1024)).toFixed(1)} MB</span>
                    </div>
                  </div>
                  
                  <button 
                    onClick={() => handleDelete(v.filename, 'video')}
                    className="absolute top-3 right-3 bg-red-500/80 hover:bg-red-600 text-white p-2 rounded-xl opacity-0 group-hover:opacity-100 transition-all duration-300 backdrop-blur-md shadow-lg z-20 hover:scale-110"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            {videos.length === 0 && <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/60"><Video size={48} className="mb-4 opacity-50" /><p className="text-lg font-medium">No video loops uploaded yet</p></div>}
          </div>
        )}

        {/* MUSIC TAB */}
        {activeTab === 'music' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="relative group border-2 border-dashed border-purple-500/30 hover:border-purple-500/80 hover:bg-purple-500/5 rounded-2xl p-8 transition-all flex flex-col items-center justify-center text-center shrink-0">
              <input 
                type="file" 
                accept="audio/*" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={(e) => handleFileUpload(e, 'music')}
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
                    onClick={() => toggleAudio(m.url)}
                    className={cn("w-12 h-12 rounded-full flex items-center justify-center transition-all shadow-md shrink-0", isPlaying ? "bg-purple-500 text-white shadow-purple-500/40" : "bg-purple-500/20 text-purple-400 group-hover:bg-purple-500 group-hover:text-white")}
                  >
                    {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-1" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-sm truncate">{m.filename}</h4>
                    <p className="text-xs text-muted-foreground mt-1 font-medium">{(m.size / (1024*1024)).toFixed(1)} MB</p>
                  </div>
                  <button 
                    onClick={() => handleDelete(m.filename, 'music')}
                    className="text-muted-foreground hover:text-red-400 transition-colors p-3 hover:bg-red-500/10 rounded-full"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              )})}
            </div>
            {music.length === 0 && <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/60"><Music size={48} className="mb-4 opacity-50" /><p className="text-lg font-medium">No audio tracks uploaded yet</p></div>}
          </div>
        )}

        {/* PEXELS TAB */}
        {activeTab === 'pexels' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col h-full animate-in fade-in">
            <div className="flex gap-4 shrink-0 bg-white/5 p-2 rounded-2xl border border-white/10 shadow-inner">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-emerald-500/70" size={20} />
                <input 
                  type="text" 
                  placeholder="Search premium stock footage (e.g. 'cyberpunk neon city')"
                  className="w-full bg-transparent border-none pl-12 pr-4 py-3 text-sm font-medium focus:outline-none focus:ring-0 text-foreground placeholder:text-muted-foreground"
                  value={pexelsQuery}
                  onChange={e => setPexelsQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handlePexelsSearch()}
                />
              </div>
              <button 
                onClick={handlePexelsSearch}
                disabled={isSearching || !pexelsQuery.trim()}
                className="px-8 py-3 rounded-xl font-bold text-sm transition-all bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 disabled:opacity-50 flex items-center gap-2"
              >
                {isSearching ? <Loader2 size={18} className="animate-spin" /> : null}
                Search
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-6">
              {pexelsResults.map(video => {
                const isDownloading = downloadingId === video.id
                return (
                  <div key={video.id} className="group relative bg-black/40 rounded-2xl border border-white/5 overflow-hidden aspect-[9/16] flex flex-col shadow-lg hover:-translate-y-1 transition-all duration-300">
                    <img src={video.thumbnail} alt="Pexels Thumbnail" className="absolute inset-0 w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-105 transition-all duration-700" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none flex flex-col justify-end p-4">
                      <p className="text-white text-xs font-bold truncate mb-3 drop-shadow-md">by {video.user?.name || 'Unknown'}</p>
                      <button 
                        onClick={() => handlePexelsDownload(video)}
                        disabled={isDownloading}
                        className="w-full py-2.5 bg-white/20 hover:bg-emerald-500 backdrop-blur-md text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 pointer-events-auto border border-white/10"
                      >
                        {isDownloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                        {isDownloading ? 'Saving...' : 'Get Asset'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
            {pexelsResults.length === 0 && !isSearching && (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground/50">
                <Globe size={48} className="mb-4 opacity-30" />
                <p className="text-lg font-medium">Search the globe for stunning visuals</p>
              </div>
            )}
          </div>
        )}

        {/* YOUTUBE TAB */}
        {activeTab === 'youtube' && (
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
                  onKeyDown={e => e.key === 'Enter' && handleYoutubeSearch()}
                />
              </div>
              <button 
                onClick={handleYoutubeSearch}
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
                  onClick={() => handleYoutubeDownload()}
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
                        onClick={() => handleYoutubeDownload(video.url)}
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
        )}

      </div>
    </div>
  )
}
