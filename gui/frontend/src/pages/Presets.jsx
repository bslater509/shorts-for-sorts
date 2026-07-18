import { useState, useEffect } from 'react'
import { Sliders, Save, Trash2, Edit2, Loader2, PaintBucket } from 'lucide-react'
import * as api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'

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

export default function Presets() {
  const { voices } = useAppStore()
  const [presets, setPresets] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  // Form State
  const [form, setForm] = useState({
    name: '',
    selected_voice: '',
    voice_speed: 1.0,
    sub_font: 'Arial',
    sub_size: 72,
    sub_color: '#FFFFFF',
    sub_highlight: '#00FFFF',
    sub_outline: '#000000',
    sub_outline_width: 5,
    sub_bold: true,
    sub_uppercase: true,
    word_pop: true,
    inactive_dim: true,
    emoji_position: 'above',
    enable_emoji_animation: true,
    emoji_scale_factor: 1.5,
    emoji_hold_duration: 0.5,
    emoji_style: 'apple',
    sub_animation_style: 'tiktok_pop'
  })

  const loadPresets = async () => {
    setIsLoading(true)
    try {
      const data = await api.fetchPresets()
      setPresets(data || {})
    } catch (err) {
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadPresets()
  }, [])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    let val = value
    if (type === 'checkbox') val = checked
    else if (['sub_size', 'sub_outline_width'].includes(name)) val = parseInt(value) || 0
    else if (name === 'voice_speed') val = parseFloat(value) || 1.0
    
    // Convert selects that represent booleans
    if (value === 'true') val = true
    if (value === 'false') val = false

    setForm(prev => ({ ...prev, [name]: val }))
  }

  const handleEdit = (name) => {
    const p = presets[name]
    if (!p) return
    setForm({
      name: name,
      selected_voice: p.selected_voice || '',
      voice_speed: p.voice_speed || 1.0,
      sub_font: p.sub_font || 'Arial',
      sub_size: p.sub_size || 72,
      sub_color: p.sub_color || '#FFFFFF',
      sub_highlight: p.sub_highlight || '#00FFFF',
      sub_outline: p.sub_outline || '#000000',
      sub_outline_width: p.sub_outline_width ?? 5,
      sub_bold: p.sub_bold !== false,
      sub_uppercase: p.sub_uppercase !== false,
      word_pop: p.word_pop !== false,
      inactive_dim: p.inactive_dim !== false,
      emoji_position: p.emoji_position || (p.enable_emojis === false ? 'none' : 'above'),
      enable_emoji_animation: p.enable_emoji_animation !== false,
      emoji_scale_factor: p.emoji_scale_factor || 1.5,
      emoji_hold_duration: p.emoji_hold_duration ?? 0.5,
      emoji_style: p.emoji_style || 'apple',
      sub_animation_style: p.sub_animation_style || 'tiktok_pop'
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleDelete = async (name) => {
    if (!confirm(`Delete preset "${name}"?`)) return
    try {
      await api.deletePreset(name)
      await loadPresets()
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) return alert("Preset Name is required.")

    setIsSaving(true)
    try {
      const payload = {
        ...form,
        enable_emojis: form.emoji_position !== 'none',
        enable_emoji_animation: form.enable_emoji_animation,
        emoji_scale_factor: form.emoji_scale_factor,
        emoji_hold_duration: form.emoji_hold_duration,
        emoji_style: form.emoji_style,
        voice_volume: 1.2,
        music_volume: 0.15,
        word_pop_scale: 1.15,
        inactive_alpha: '88',
      }
      if (form.emoji_position === 'none') {
        payload.emoji_position = 'none'
      }

      await api.savePreset(payload)
      alert("Preset saved successfully!")
      await loadPresets()
    } catch (err) {
      alert(`Save failed: ${err.message}`)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)]">
      <header className="shrink-0">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Sliders className="text-blue-500" />
          Preset Templates Manager
        </h1>
        <p className="text-muted-foreground mt-1">Configure and save visual typography subtitles, layouts, and sound presets</p>
      </header>

      <div className="flex-1 md:overflow-hidden flex flex-col lg:flex-row gap-6">
        {/* Editor Form */}
        <div className="flex-1 bg-card border border-border rounded-xl shadow-sm flex flex-col md:overflow-hidden">
          <div className="p-4 border-b border-border bg-secondary/30">
            <h2 className="font-semibold flex items-center gap-2">
              <PaintBucket size={18} className="text-blue-500" />
              Preset Designer
            </h2>
          </div>
          
          <div className="flex-1 md:overflow-y-auto p-6">
            <form id="preset-form" onSubmit={handleSave} className="space-y-8">
              
              <div className="space-y-4">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-semibold">Preset Name</label>
                  <input type="text" name="name" value={form.name} onChange={handleChange} placeholder="e.g. Cinematic Yellow Pop" className="input-base text-lg font-medium" required />
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">Subtitle Typography</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Font Family</label>
                    <select name="sub_font" value={form.sub_font} onChange={handleChange} className="input-base">
                      {['Arial', 'Impact', 'Georgia', 'Times New Roman', 'Courier New', 'Trebuchet MS', 'Verdana', 'Montserrat', 'Roboto', 'Open Sans', 'Inter', 'Bebas Neue', 'Anton', 'Bangers', 'Poppins', 'Raleway'].map(f => (
                        <option key={f} value={f}>{f}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Font Size (px)</label>
                    <input type="number" name="sub_size" value={form.sub_size} onChange={handleChange} className="input-base" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Font Weight</label>
                    <select name="sub_bold" value={form.sub_bold.toString()} onChange={handleChange} className="input-base">
                      <option value="true">Bold</option>
                      <option value="false">Normal</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Text Case</label>
                    <select name="sub_uppercase" value={form.sub_uppercase.toString()} onChange={handleChange} className="input-base">
                      <option value="true">ALL CAPS</option>
                      <option value="false">Normal Case</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">Colors & Styling</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  {[
                    { label: 'Primary Text Color', name: 'sub_color' },
                    { label: 'Active Word Highlight', name: 'sub_highlight' },
                    { label: 'Outline Color', name: 'sub_outline' }
                  ].map(colorField => (
                    <div key={colorField.name} className="flex flex-col gap-2">
                      <label className="text-sm font-medium">{colorField.label}</label>
                      <div className="flex items-center gap-2">
                        <input type="color" name={colorField.name} value={form[colorField.name]} onChange={handleChange} className="w-10 h-10 rounded cursor-pointer bg-transparent border-0 p-0" />
                        <input type="text" name={colorField.name} value={form[colorField.name]} onChange={handleChange} className="input-base flex-1 uppercase font-mono" />
                      </div>
                    </div>
                  ))}
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Outline Border Width</label>
                    <input type="number" name="sub_outline_width" value={form.sub_outline_width} onChange={handleChange} className="input-base" />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">Animation & Emojis</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Animation Scheme</label>
                    <select name="sub_animation_style" value={form.sub_animation_style} onChange={handleChange} className="input-base">
                      {ANIMATIONS.map(a => (
                        <option key={a.value} value={a.value}>{a.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Dynamic Emojis Position</label>
                    <select name="emoji_position" value={form.emoji_position} onChange={handleChange} className="input-base">
                      <option value="above">Above Text Line</option>
                      <option value="same_line">Next to Word</option>
                      <option value="none">Disabled (No emojis)</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Emoji Animation</label>
                    <select name="enable_emoji_animation" value={form.enable_emoji_animation.toString()} onChange={handleChange} className="input-base">
                      <option value="true">Enabled (pop/bounce/float/fade/shake)</option>
                      <option value="false">Disabled (static emojis)</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Emoji Size Scale</label>
                    <input type="number" name="emoji_scale_factor" value={form.emoji_scale_factor} onChange={handleChange} step="0.1" min="0.5" max="3.0" className="input-base" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Emoji Hold (seconds)</label>
                    <input type="number" name="emoji_hold_duration" value={form.emoji_hold_duration} onChange={handleChange} step="0.1" min="0" max="2.0" className="input-base" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Emoji Style</label>
                    <select name="emoji_style" value={form.emoji_style} onChange={handleChange} className="input-base">
                      <option value="apple">Apple</option>
                      <option value="twemoji">Twemoji (Twitter)</option>
                      <option value="google">Google</option>
                      <option value="facebook">Facebook</option>
                      <option value="openmoji">OpenMoji</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Word Scale Pop-up</label>
                    <select name="word_pop" value={form.word_pop.toString()} onChange={handleChange} className="input-base">
                      <option value="true">Enabled (1.15x scale)</option>
                      <option value="false">Disabled</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Dim Inactive Words</label>
                    <select name="inactive_dim" value={form.inactive_dim.toString()} onChange={handleChange} className="input-base">
                      <option value="true">Dim (opacity: 50%)</option>
                      <option value="false">No dimming</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">Default Media</h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Default Speaker Voice</label>
                    <select name="selected_voice" value={form.selected_voice} onChange={handleChange} className="input-base">
                      <option value="">(None)</option>
                      {voices.map(v => (
                        <option key={v.value} value={v.value}>{v.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Voice Speed Factor</label>
                    <input type="number" step="0.05" name="voice_speed" value={form.voice_speed} onChange={handleChange} className="input-base" />
                  </div>
                </div>
              </div>

            </form>
          </div>
          
          <div className="p-4 border-t border-border bg-secondary/30">
            <button 
              type="submit"
              form="preset-form"
              disabled={isSaving}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium shadow-md shadow-blue-500/20 transition-all disabled:opacity-50"
            >
              {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save Preset Template
            </button>
          </div>
        </div>

        {/* Presets List */}
        <div className="w-full lg:w-80 bg-card border border-border rounded-xl shadow-sm flex flex-col shrink-0">
          <div className="p-4 border-b border-border bg-secondary/30">
            <h2 className="font-semibold">Saved Presets</h2>
          </div>
          <div className="flex-1 md:overflow-y-auto p-4 space-y-3">
            {isLoading ? (
              <div className="flex justify-center p-4"><Loader2 size={24} className="animate-spin text-muted-foreground" /></div>
            ) : Object.keys(presets).length > 0 ? (
              Object.keys(presets).map(name => {
                const p = presets[name]
                return (
                  <div key={name} className="bg-secondary/50 border border-border rounded-lg p-3 hover:border-blue-500/30 transition-colors">
                    <h4 className="font-semibold text-sm truncate" title={name}>{name}</h4>
                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {p.sub_animation_style} • {p.sub_font}
                    </p>
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
                      <button 
                        onClick={() => handleEdit(name)}
                        className="flex-1 flex items-center justify-center gap-1.5 py-1 bg-background hover:bg-blue-500 hover:text-white border border-border hover:border-blue-500 rounded text-xs font-medium transition-colors"
                      >
                        <Edit2 size={12} /> Edit
                      </button>
                      <button 
                        onClick={() => handleDelete(name)}
                        className="flex-1 flex items-center justify-center gap-1.5 py-1 bg-background hover:bg-red-500 hover:text-white border border-border hover:border-red-500 rounded text-xs font-medium transition-colors"
                      >
                        <Trash2 size={12} /> Delete
                      </button>
                    </div>
                  </div>
                )
              })
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No presets saved yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
