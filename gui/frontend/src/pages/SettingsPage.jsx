import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, Key, Cpu, Mic, Video, Loader2, Activity, Plus, Trash, CheckCircle, RefreshCw } from 'lucide-react'
import * as api from '@/lib/api'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    llm_profiles: [],
    active_llm_profile_id: '',
    max_words: 400,
    system_prompt: '',
    pexels_api_key: '',
    local_whisper: true,
    local_whisper_model: 'tiny',
    whisper_api_key: '',
    whisper_base_url: '',
    render_resolution: '720p',
    render_preset: 'fast',
    video_encoder: 'libx264',
    words_per_screen: '3',
    max_workers: 1,
    llm_max_workers: 5,
    sentry_dsn: '',
    tiktok_sessionid: '',
  })
  
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [availableModels, setAvailableModels] = useState({})
  const [isFetchingModels, setIsFetchingModels] = useState({})
  const [notificationStatus, setNotificationStatus] = useState(
    "Notification" in window ? Notification.permission : "unsupported"
  );

  const requestNotificationPermission = async () => {
    if (!("Notification" in window)) return;
    const permission = await Notification.requestPermission();
    setNotificationStatus(permission);
    if (permission === 'granted') {
      alert("Notifications enabled successfully!");
    } else {
      alert("Notification permission denied or dismissed.");
    }
  };

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

  const handleProfileChange = (id, field, value) => {
    setSettings(prev => ({
      ...prev,
      llm_profiles: prev.llm_profiles.map(p => p.id === id ? { ...p, [field]: value } : p)
    }))
  }
  
  const handleAddProfile = () => {
    const newId = crypto.randomUUID()
    setSettings(prev => ({
      ...prev,
      llm_profiles: [
        ...(prev.llm_profiles || []), 
        { id: newId, name: 'New Profile', api_key: '', base_url: '', model: 'gpt-4o-mini' }
      ],
      active_llm_profile_id: prev.active_llm_profile_id ? prev.active_llm_profile_id : newId
    }))
  }
  
  const handleDeleteProfile = (id) => {
    setSettings(prev => ({
      ...prev,
      llm_profiles: prev.llm_profiles.filter(p => p.id !== id)
    }))
  }
  
  const handleSetActiveProfile = (id) => {
    setSettings(prev => ({ ...prev, active_llm_profile_id: id }))
  }

  const handleFetchModels = async (profile) => {
    setIsFetchingModels(prev => ({ ...prev, [profile.id]: true }))
    try {
      const res = await api.fetchLLMModels(profile.api_key, profile.base_url)
      setAvailableModels(prev => ({ ...prev, [profile.id]: res.models }))
    } catch (err) {
      alert(err.message || 'Failed to fetch models')
    } finally {
      setIsFetchingModels(prev => ({ ...prev, [profile.id]: false }))
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const payload = {
        ...settings,
        max_words: parseInt(settings.max_words) || 400,
        max_workers: parseInt(settings.max_workers) || 1,
        llm_max_workers: parseInt(settings.llm_max_workers) || 5,
        llm_temp_script: parseFloat(settings.llm_temp_script ?? 0.7),
        llm_temp_metadata: parseFloat(settings.llm_temp_metadata ?? 0.7),
        llm_temp_keywords: parseFloat(settings.llm_temp_keywords ?? 0.7)
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
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Cpu className="text-blue-500" size={20} />
              LLM Profiles
            </h3>
            <button onClick={handleAddProfile} className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 rounded-lg text-sm font-medium transition-colors">
              <Plus size={16} /> Add Profile
            </button>
          </div>
          
          <div className="space-y-4">
            {(!settings.llm_profiles || settings.llm_profiles.length === 0) ? (
               <p className="text-sm text-muted-foreground italic">No profiles configured. Add one above.</p>
            ) : (
               settings.llm_profiles.map((profile, index) => (
                 <div key={profile.id} className={`p-4 border rounded-lg space-y-4 ${settings.active_llm_profile_id === profile.id ? 'border-blue-500 bg-blue-500/5' : 'border-border'}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <input 
                          type="text" 
                          value={profile.name} 
                          onChange={(e) => handleProfileChange(profile.id, 'name', e.target.value)}
                          className="font-medium bg-transparent border-b border-dashed border-muted-foreground/30 focus:border-blue-500 focus:outline-none"
                          placeholder="Profile Name"
                        />
                        {settings.active_llm_profile_id === profile.id && (
                          <span className="flex items-center gap-1 text-xs font-semibold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded-full"><CheckCircle size={12}/> Active</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                         {settings.active_llm_profile_id !== profile.id && (
                           <button onClick={() => handleSetActiveProfile(profile.id)} className="text-xs px-3 py-1.5 border border-border hover:bg-accent rounded-md">
                             Set Active
                           </button>
                         )}
                         <button onClick={() => handleDeleteProfile(profile.id)} className="text-red-500 hover:bg-red-500/10 p-1.5 rounded-md" title="Delete Profile">
                           <Trash size={16} />
                         </button>
                      </div>
                    </div>
                    
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div className="flex flex-col gap-2">
                        <label className="text-xs font-medium text-muted-foreground">API Key (Optional if env set)</label>
                        <input type="password" value={profile.api_key} onChange={(e) => handleProfileChange(profile.id, 'api_key', e.target.value)} placeholder="sk-..." className="input-base text-sm py-1.5" />
                      </div>
                      <div className="flex flex-col gap-2">
                        <label className="text-xs font-medium text-muted-foreground">API Base URL</label>
                        <input type="text" value={profile.base_url} onChange={(e) => handleProfileChange(profile.id, 'base_url', e.target.value)} placeholder="https://api.openai.com/v1" className="input-base text-sm py-1.5" />
                      </div>
                      <div className="flex flex-col gap-2">
                        <label className="text-xs font-medium text-muted-foreground flex justify-between items-center">
                          Model Name
                          <button 
                            onClick={() => handleFetchModels(profile)} 
                            disabled={isFetchingModels[profile.id]}
                            className="text-blue-500 hover:underline flex items-center gap-1 disabled:opacity-50"
                          >
                            {isFetchingModels[profile.id] ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                            Fetch Models
                          </button>
                        </label>
                        {availableModels[profile.id] && availableModels[profile.id].length > 0 ? (
                          <select 
                            value={profile.model} 
                            onChange={(e) => handleProfileChange(profile.id, 'model', e.target.value)}
                            className="input-base text-sm py-1.5"
                          >
                            <option value="">-- Select a Model --</option>
                            {availableModels[profile.id].map(m => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                          </select>
                        ) : (
                          <input type="text" value={profile.model} onChange={(e) => handleProfileChange(profile.id, 'model', e.target.value)} className="input-base text-sm py-1.5" placeholder="e.g. gpt-4o" />
                        )}
                      </div>
                    </div>
                 </div>
               ))
            )}
          </div>
          
          <div className="grid sm:grid-cols-2 gap-4 pt-4 border-t border-border mt-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Max Script Words Length</label>
              <input type="number" name="max_words" value={settings.max_words} onChange={handleChange} className="input-base" />
            </div>
            <div className="flex flex-col gap-2 md:col-span-2">
              <label className="text-sm font-medium">System Prompt</label>
              <textarea 
                name="system_prompt" 
                value={settings.system_prompt || ''} 
                onChange={handleChange} 
                className="input-base min-h-[120px] font-mono text-sm" 
                placeholder="You are an elite TikTok and YouTube Shorts scriptwriter known for creating viral, high-retention content..."
              />
              <p className="text-xs text-muted-foreground">
                You can use {'{max_words}'} and {'{max_words_seconds}'} as variables in the prompt.
              </p>
            </div>
            
            <div className="flex flex-col gap-2 md:col-span-2 mt-2">
              <label className="text-sm font-medium">LLM Temperatures</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border border-border rounded-lg p-4 bg-muted/30">
                <div className="flex flex-col gap-2">
                  <label className="text-xs text-muted-foreground font-medium">Script Generation</label>
                  <input type="number" step="0.1" min="0.0" max="2.0" name="llm_temp_script" value={settings.llm_temp_script !== undefined ? settings.llm_temp_script : 0.7} onChange={handleChange} className="input-base" />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-xs text-muted-foreground font-medium">Metadata (Title/Hashtags)</label>
                  <input type="number" step="0.1" min="0.0" max="2.0" name="llm_temp_metadata" value={settings.llm_temp_metadata !== undefined ? settings.llm_temp_metadata : 0.7} onChange={handleChange} className="input-base" />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-xs text-muted-foreground font-medium">Keyword Extraction</label>
                  <input type="number" step="0.1" min="0.0" max="2.0" name="llm_temp_keywords" value={settings.llm_temp_keywords !== undefined ? settings.llm_temp_keywords : 0.7} onChange={handleChange} className="input-base" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Third Party */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Key className="text-emerald-500" size={20} />
            Third Party APIs & Integrations
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Pexels API Key (For Auto-B-Roll)</label>
              <input type="password" name="pexels_api_key" value={settings.pexels_api_key} onChange={handleChange} placeholder="Optional" className="input-base" />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Sentry DSN (Error Tracking)</label>
              <input type="text" name="sentry_dsn" value={settings.sentry_dsn || ''} onChange={handleChange} placeholder="https://..." className="input-base" />
            </div>
            <div className="flex flex-col gap-2 md:col-span-2">
              <label className="text-sm font-medium">TikTok Session ID (For Auto-Uploading)</label>
              <div className="flex gap-2">
                <input 
                  type="password" 
                  name="tiktok_sessionid" 
                  value={settings.tiktok_sessionid || ''} 
                  onChange={handleChange} 
                  placeholder="Paste sessionid cookie or login..." 
                  className="input-base flex-1" 
                />
                <button 
                  onClick={async () => {
                    try {
                      const res = await api.loginTikTok();
                      alert(res.message || "Browser opened! Please log in.");
                    } catch (e) {
                      alert("Error: " + e.message);
                    }
                  }}
                  className="px-4 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-medium text-sm transition-colors whitespace-nowrap"
                >
                  Login to TikTok
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Whisper Config */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Mic className="text-purple-500" size={20} />
            Whisper Transcription (Subtitles)
          </h3>
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Words per Screen</label>
              <select 
                name="words_per_screen" 
                value={settings.words_per_screen || '3'} 
                onChange={handleChange} 
                className="input-base"
              >
                <option value="1">1 Word (TikTok Style)</option>
                <option value="3">3 Words (Short Phrases)</option>
                <option value="sentence">Sentence (Long Chunks)</option>
                <option value="random">Randomize (Batch Generator Only)</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
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
                <option value="libx265">libx265 (HEVC CPU - Default)</option>
                <option value="libx264">libx264 (CPU)</option>
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

          <div className="pt-4 border-t border-border mt-4">
            <h4 className="text-sm font-medium mb-2">Web Notifications</h4>
            <div className="flex items-center gap-4">
              <p className="text-xs text-muted-foreground flex-1">
                Enable background notifications for job completions. (On iOS, add this page to your Home Screen first).
                <br />
                Status: <strong>{notificationStatus}</strong>
              </p>
              {notificationStatus !== 'granted' && notificationStatus !== 'unsupported' && (
                <button 
                  onClick={requestNotificationPermission}
                  className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium text-sm transition-colors whitespace-nowrap shadow-sm"
                >
                  Enable Notifications
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
