import { useState, useEffect, useRef } from 'react'
import { Video, Music, Globe, PlaySquare } from 'lucide-react'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import VideosTab from '@/components/media/VideosTab'
import MusicTab from '@/components/media/MusicTab'
import PexelsTab from '@/components/media/PexelsTab'
import YouTubeTab from '@/components/media/YouTubeTab'

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
        {activeTab === 'videos' && (
          <VideosTab
            videos={videos}
            onUpload={handleFileUpload}
            onDelete={handleDelete}
            isUploading={isUploading}
          />
        )}

        {activeTab === 'music' && (
          <MusicTab
            music={music}
            onUpload={handleFileUpload}
            onDelete={handleDelete}
            isUploading={isUploading}
            playingAudio={playingAudio}
            onToggleAudio={toggleAudio}
          />
        )}

        {activeTab === 'pexels' && (
          <PexelsTab
            pexelsQuery={pexelsQuery}
            setPexelsQuery={setPexelsQuery}
            pexelsResults={pexelsResults}
            isSearching={isSearching}
            downloadingId={downloadingId}
            onSearch={handlePexelsSearch}
            onDownload={handlePexelsDownload}
          />
        )}

        {activeTab === 'youtube' && (
          <YouTubeTab
            youtubeQuery={youtubeQuery}
            setYoutubeQuery={setYoutubeQuery}
            youtubeResults={youtubeResults}
            youtubeUrl={youtubeUrl}
            setYoutubeUrl={setYoutubeUrl}
            youtubeDownscale={youtubeDownscale}
            setYoutubeDownscale={setYoutubeDownscale}
            isYoutubeSearching={isYoutubeSearching}
            isYoutubeDownloading={isYoutubeDownloading}
            onSearch={handleYoutubeSearch}
            onDownload={handleYoutubeDownload}
          />
        )}
      </div>
    </div>
  )
}
