import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, Key, Cpu, Mic, Video, Loader2, Activity } from 'lucide-react'
import * as api from '@/lib/api'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    api_key: '',
    base_url: '',
    model: 'gpt-4o-mini',
    max_words: 130,
    pexels_api_key: '',
    local_whisper: true,
    local_whisper_model: 'tiny',
    whisper_api_key: '',
    whisper_base_url: '',
    render_resolution: '1080p',
    render_preset: 'veryfast',
    video_encoder: 'libx264',
    max_workers: 1,
    llm_max_workers: 5,
  })
  
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await api.fetchSettings()
        setSettings(prev => ({ ...prev, ...data }))
      } catch (err) {
        console.error("Failed to load settings:", err)
      } finally {
        setIsLoading(false)
      }
    }
    loadSettings()
  }, [])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setSettings(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const payload = {
        ...settings,
        max_words: parseInt(settings.max_words) || 130,
        max_workers: parseInt(settings.max_workers) || 1,
        llm_max_workers: parseInt(settings.llm_max_workers) || 5
      }
      await api.saveSettings(payload)
      alert('Settings saved successfully!')
    } catch (err) {
      alert(`Error saving settings: ${err.message}`)
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-6rem)] items-center justify-center text-muted-foreground">
        <Loader2 size={32} className="animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)]">
      <header className="shrink-0 flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <SettingsIcon className="text-blue-500" />
            System Configuration
          </h1>
          <p className="text-muted-foreground mt-1">Configure models, API keys, Whisper transcription, and FFmpeg render settings.</p>
        </div>
        
        <button 
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-6 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium shadow-md shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          Save Settings
        </button>
      </header>

      <div className="flex-1 md:overflow-y-auto pr-2 space-y-6 pb-6">
        {/* LLM Config */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Cpu className="text-blue-500" size={20} />
            LLM Script Generator (OpenAI Format)
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">API Key (Optional if env set)</label>
              <input type="password" name="api_key" value={settings.api_key} onChange={handleChange} placeholder="sk-..." className="input-base" />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">API Base URL</label>
              <input type="text" name="base_url" value={settings.base_url} onChange={handleChange} placeholder="https://api.openai.com/v1" className="input-base" />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Script Generator Model</label>
              <input type="text" name="model" value={settings.model} onChange={handleChange} className="input-base" />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Max Script Words Length</label>
              <input type="number" name="max_words" value={settings.max_words} onChange={handleChange} className="input-base" />
            </div>
          </div>
        </div>

        {/* Third Party */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Key className="text-emerald-500" size={20} />
            Third Party APIs
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Pexels API Key (For Auto-B-Roll)</label>
              <input type="password" name="pexels_api_key" value={settings.pexels_api_key} onChange={handleChange} placeholder="Optional" className="input-base" />
            </div>
          </div>
        </div>

        {/* Whisper Config */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Mic className="text-purple-500" size={20} />
            Whisper Transcription (Subtitles)
          </h3>
          <div className="flex flex-col gap-2 mb-4">
            <label className="text-sm font-medium">Transcription Engine</label>
            <select 
              name="local_whisper" 
              value={settings.local_whisper} 
              onChange={(e) => handleChange({ target: { name: 'local_whisper', value: e.target.value === 'true', type: 'boolean' } })} 
              className="input-base max-w-xs"
            >
              <option value="true">Local CPU/GPU (faster-whisper)</option>
              <option value="false">OpenAI API (Cloud)</option>
            </select>
          </div>

          {settings.local_whisper ? (
            <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Local Model Size</label>
                <select name="local_whisper_model" value={settings.local_whisper_model} onChange={handleChange} className="input-base">
                  <option value="tiny">tiny (fastest, lowest accuracy)</option>
                  <option value="base">base</option>
                  <option value="small">small (recommended)</option>
                  <option value="medium">medium</option>
                  <option value="large-v3">large-v3 (slowest, highest accuracy)</option>
                </select>
              </div>
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Whisper API Key</label>
                <input type="password" name="whisper_api_key" value={settings.whisper_api_key} onChange={handleChange} className="input-base" />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Whisper API URL</label>
                <input type="text" name="whisper_base_url" value={settings.whisper_base_url} onChange={handleChange} className="input-base" />
              </div>
            </div>
          )}
        </div>

        {/* FFmpeg Config */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Video className="text-orange-500" size={20} />
            Render & FFmpeg Configuration
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Vertical Resolution</label>
              <select name="render_resolution" value={settings.render_resolution} onChange={handleChange} className="input-base">
                <option value="720p">720p (720x1280)</option>
                <option value="1080p">1080p (1080x1920) - Standard</option>
                <option value="1440p">1440p (1440x2560)</option>
                <option value="4k">4K (2160x3840)</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">FFmpeg Preset (Speed vs Size)</label>
              <select name="render_preset" value={settings.render_preset} onChange={handleChange} className="input-base">
                <option value="ultrafast">ultrafast</option>
                <option value="superfast">superfast</option>
                <option value="veryfast">veryfast (recommended)</option>
                <option value="faster">faster</option>
                <option value="fast">fast</option>
                <option value="medium">medium</option>
                <option value="slow">slow</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Video Encoder</label>
              <select name="video_encoder" value={settings.video_encoder} onChange={handleChange} className="input-base">
                <option value="libx264">libx264 (CPU - Default)</option>
                <option value="h264_nvenc">h264_nvenc (NVIDIA GPU)</option>
                <option value="hevc_nvenc">hevc_nvenc (NVIDIA GPU H.265)</option>
                <option value="h264_amf">h264_amf (AMD GPU)</option>
                <option value="h264_qsv">h264_qsv (Intel QuickSync)</option>
              </select>
            </div>
          </div>
        </div>

        {/* System & Performance Config */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Activity className="text-blue-400" size={20} />
            System & Performance
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Max Parallel Operations (CPU/Rendering)</label>
              <input type="number" min="1" max="64" name="max_workers" value={settings.max_workers || ''} onChange={handleChange} placeholder="Default: CPU Count" className="input-base" />
              <p className="text-xs text-muted-foreground">Controls how many videos render/process at once.</p>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Max Parallel LLM API Requests</label>
              <input type="number" min="1" max="64" name="llm_max_workers" value={settings.llm_max_workers || ''} onChange={handleChange} placeholder="Default: 5" className="input-base" />
              <p className="text-xs text-muted-foreground">Controls how many LLM scripts generate concurrently.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
