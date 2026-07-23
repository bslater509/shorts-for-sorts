import { Volume2 } from 'lucide-react'

export default function AudioDefaultsSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Volume2 className="text-pink-500" size={20} />
        Audio Defaults
      </h3>
      <div className="grid sm:grid-cols-3 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Voice Speed</label>
          <input
            type="number"
            min="0.5"
            max="2"
            step="0.05"
            name="voice_speed"
            value={settings.voice_speed ?? 1.0}
            onChange={onChange}
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">TTS playback speed (1.0 = normal).</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Voice Volume</label>
          <input
            type="number"
            min="0"
            max="5"
            step="0.1"
            name="voice_volume"
            value={settings.voice_volume ?? 1.0}
            onChange={onChange}
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Voice audio gain multiplier.</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Music Volume</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            name="music_volume"
            value={settings.music_volume ?? 0.15}
            onChange={onChange}
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Background music volume (0-1).</p>
        </div>
      </div>
    </div>
  )
}
