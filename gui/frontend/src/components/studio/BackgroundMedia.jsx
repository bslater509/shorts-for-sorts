import { Video, Music, MonitorPlay, Layout } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'

export default function BackgroundMedia() {
  const { appState, updateAppState, saveCurrentState } = useAppStore()

  // Helper to extract filename
  const getBaseName = (path) => path ? path.split(/[/\\]/).pop() : null

  const topVideo = getBaseName(appState.bg_video_path) || 'Random Selection'
  const bottomVideo = getBaseName(appState.bg_video_bottom_path) || 'None (Disable Split Screen)'
  const music = getBaseName(appState.bg_music_path) || 'None'

  const handleDisableSplit = async () => {
    updateAppState({ bg_video_bottom_path: null })
    await saveCurrentState()
  }

  // Placeholder for asset picker modal logic
  const handleOpenPicker = (type) => {
    // TODO: Implement Media Modal Picker
    alert(`Open ${type} picker modal (To be implemented in Media Manager migration)`)
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <MonitorPlay className="text-blue-500" />
          Configure Background Media
        </h2>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Top Video Picker */}
          <div className="bg-secondary/30 border border-border rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-center gap-2 text-foreground font-medium">
              <Video size={18} className="text-muted-foreground" />
              <h4>Top Background (Primary)</h4>
            </div>
            
            <div className="bg-background border border-border rounded-lg p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-3 overflow-hidden pr-4">
                <div className="w-10 h-10 rounded-md bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Video size={20} className="text-blue-500" />
                </div>
                <span className="text-sm font-medium truncate">{topVideo}</span>
              </div>
              <button 
                onClick={() => handleOpenPicker('top')}
                className="shrink-0 px-4 py-1.5 bg-secondary hover:bg-secondary/80 border border-border rounded-md text-sm font-medium transition-colors"
              >
                Choose File
              </button>
            </div>
          </div>
          
          {/* Bottom Video Picker */}
          <div className="bg-secondary/30 border border-border rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-center gap-2 text-foreground font-medium">
              <Layout size={18} className="text-muted-foreground" />
              <h4>Bottom Background (Split Screen)</h4>
            </div>
            
            <div className="bg-background border border-border rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
              <div className="flex items-center gap-3 overflow-hidden w-full">
                <div className="w-10 h-10 rounded-md bg-purple-500/10 flex items-center justify-center shrink-0">
                  <Video size={20} className="text-purple-500" />
                </div>
                <span className="text-sm font-medium truncate">{bottomVideo}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                <button 
                  onClick={() => handleOpenPicker('bottom')}
                  className="flex-1 sm:flex-none px-4 py-1.5 bg-secondary hover:bg-secondary/80 border border-border rounded-md text-sm font-medium transition-colors"
                >
                  Choose File
                </button>
                <button 
                  onClick={handleDisableSplit}
                  disabled={!appState.bg_video_bottom_path}
                  className="px-3 py-1.5 text-red-500 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 rounded-md text-sm font-medium transition-colors disabled:opacity-30"
                  title="Disable split screen"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border"></div>
        </div>
      </div>

      {/* Music Picker */}
      <div className="bg-secondary/30 border border-border rounded-xl p-5 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-foreground font-medium">
          <Music size={18} className="text-muted-foreground" />
          <h4>Background Audio Track</h4>
        </div>
        
        <div className="bg-background border border-border rounded-lg p-4 flex items-center justify-between shadow-sm max-w-2xl">
          <div className="flex items-center gap-3 overflow-hidden pr-4">
            <div className="w-10 h-10 rounded-md bg-emerald-500/10 flex items-center justify-center shrink-0">
              <Music size={20} className="text-emerald-500" />
            </div>
            <span className="text-sm font-medium truncate">{music}</span>
          </div>
          <button 
            onClick={() => handleOpenPicker('music')}
            className="shrink-0 px-4 py-1.5 bg-secondary hover:bg-secondary/80 border border-border rounded-md text-sm font-medium transition-colors"
          >
            Choose File
          </button>
        </div>
      </div>
    </div>
  )
}
