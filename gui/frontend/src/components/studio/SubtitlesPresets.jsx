import { Type, Layers } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import { cn } from '@/lib/utils'

const ANIMATIONS = [
  { value: "tiktok_pop", label: "TikTok Classic (WordPop)" },
  { value: "karaoke_sweep", label: "Karaoke Sweep (Smooth)" },
  { value: "bouncy_bounce", label: "Bouncy Jump (Kinetic)" },
  { value: "cinematic_zoom", label: "Cinematic Zoom (Fade)" },
  { value: "glow_shake", label: "Glow Shake (Tilt)" },
  { value: "neon_flicker", label: "Neon Flicker (Flicker)" },
  { value: "pulse_grow", label: "Pulse Grow (Hype)" },
  { value: "fade_in_slide", label: "Fade-in Slide (Smooth)" },
  { value: "typewriter_swipe", label: "Typewriter Swipe (Reveal)" }
]

export default function SubtitlesPresets() {
  const { appState, presets, voices, updateAppState, saveCurrentState, applyPreset } = useAppStore()

  const handleAnimationChange = async (e) => {
    updateAppState({ sub_animation_style: e.target.value, loaded_preset_name: null })
    await saveCurrentState()
  }

  const handleVoiceChange = async (e) => {
    updateAppState({ selected_voice: e.target.value, loaded_preset_name: null })
    await saveCurrentState()
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <Layers className="text-blue-500" />
          Preset Templates
        </h2>
        
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {Object.keys(presets || {}).map((presetName) => {
            const isActive = appState.loaded_preset_name === presetName
            return (
              <button
                key={presetName}
                onClick={() => applyPreset(presetName)}
                className={cn(
                  "p-4 rounded-xl border text-sm font-medium transition-all text-center break-words shadow-sm",
                  isActive 
                    ? "bg-blue-500/10 border-blue-500 text-blue-500 ring-1 ring-blue-500" 
                    : "bg-card border-border text-foreground hover:border-blue-500/50 hover:bg-secondary/50"
                )}
              >
                {presetName}
              </button>
            )
          })}
          {Object.keys(presets || {}).length === 0 && (
            <p className="text-muted-foreground text-sm col-span-full">No presets available. Create one in the Presets tab.</p>
          )}
        </div>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border"></div>
        </div>
        <div className="relative flex justify-center">
          <span className="bg-card px-2 text-sm text-muted-foreground">Manual Styling</span>
        </div>
      </div>

      <div>
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <Type className="text-blue-500" />
          Subtitles & Voice Styling
        </h2>
        
        <div className="grid sm:grid-cols-2 gap-6">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-foreground">TTS Voice Speaker</label>
            <select 
              className="bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 shadow-sm"
              value={appState.selected_voice || ''}
              onChange={handleVoiceChange}
            >
              {voices.map(v => (
                <option key={v.value} value={v.value}>{v.name}</option>
              ))}
            </select>
          </div>
          
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-foreground">Subtitle Animation</label>
            <select 
              className="bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 shadow-sm"
              value={appState.sub_animation_style || 'tiktok_pop'}
              onChange={handleAnimationChange}
            >
              {ANIMATIONS.map(anim => (
                <option key={anim.value} value={anim.value}>{anim.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
