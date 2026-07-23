import { useState, useEffect } from 'react'
import { Sliders, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'
import PresetForm from '../components/presets/PresetForm'
import PresetListItem from '../components/presets/PresetListItem'
import { ANIMATIONS } from '../components/presets/AnimationSelector'

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
        <PresetForm
          form={form}
          onChange={handleChange}
          animations={ANIMATIONS}
          voices={voices}
          onSave={handleSave}
          isSaving={isSaving}
        />

        {/* Presets List */}
        <div className="w-full lg:w-80 bg-card border border-border rounded-xl shadow-sm flex flex-col shrink-0">
          <div className="p-4 border-b border-border bg-secondary/30">
            <h2 className="font-semibold">Saved Presets</h2>
          </div>
          <div className="flex-1 md:overflow-y-auto p-4 space-y-3">
            {isLoading ? (
              <div className="flex justify-center p-4"><Loader2 size={24} className="animate-spin text-muted-foreground" /></div>
            ) : Object.keys(presets).length > 0 ? (
              Object.keys(presets).map(name => (
                <PresetListItem
                  key={name}
                  preset={presets[name]}
                  name={name}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No presets saved yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
