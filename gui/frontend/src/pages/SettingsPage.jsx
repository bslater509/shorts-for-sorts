import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, Loader2 } from 'lucide-react'
import * as api from '@/lib/api'
import LLMProfilesSection from '../components/settings/LLMProfilesSection'
import AIGenerationSection from '../components/settings/AIGenerationSection'
import ThirdPartySection from '../components/settings/ThirdPartySection'
import WhisperSection from '../components/settings/WhisperSection'
import FFmpegSection from '../components/settings/FFmpegSection'
import AudioDefaultsSection from '../components/settings/AudioDefaultsSection'
import SystemPerformanceSection from '../components/settings/SystemPerformanceSection'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    llm_profiles: [],
    active_llm_profile_id: '',
    pexels_api_key: '',
    local_whisper: true,
    local_whisper_model: 'tiny',
    whisper_api_key: '',
    whisper_base_url: '',
    render_resolution: '720p',
    render_preset: 'fast',
    video_encoder: 'libx264',
    max_workers: 1,
    llm_max_workers: 5,
    sentry_dsn: '',
    tiktok_sessionid: '',
    system_prompt: '',
    max_words: 400,
    default_batch_size: 1,
    words_per_screen: '3',
    llm_temp_script: 0.7,
    llm_temp_metadata: 0.7,
    llm_temp_keywords: 0.7,
    voice_speed: 1.0,
    voice_volume: 1.0,
    music_volume: 0.15,
  })
  
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
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
        setLoadError(null)
      } catch (err) {
        console.error("Failed to load settings:", err)
        setLoadError(err.message || 'Could not fetch settings from server')
      } finally {
        setIsLoading(false)
      }
    }
    loadSettings()
  }, [])

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    let val = type === 'checkbox' ? checked : value
    if (name === 'local_whisper') val = value === 'true'
    setSettings(prev => ({
      ...prev,
      [name]: val
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
  
  const handleDeleteProfile = async (id) => {
    const isDeletingActive = settings.active_llm_profile_id === id
    const updated = {
      ...settings,
      llm_profiles: settings.llm_profiles.filter(p => p.id !== id),
      active_llm_profile_id: isDeletingActive ? '' : settings.active_llm_profile_id,
    }
    setSettings(updated)
    try {
      await api.saveSettings(updated)
    } catch (err) {
      console.error('Failed to save after deleting profile:', err)
    }
  }
  
  const handleSetActiveProfile = async (id) => {
    const updated = { ...settings, active_llm_profile_id: id }
    setSettings(updated)
    try {
      await api.saveSettings(updated)
    } catch (err) {
      console.error('Failed to save active profile:', err)
    }
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
        max_workers: parseInt(settings.max_workers) || 1,
        llm_max_workers: parseInt(settings.llm_max_workers) || 5,
        default_batch_size: parseInt(settings.default_batch_size) || 1,
        max_words: parseInt(settings.max_words) || 400,
        words_per_screen: settings.words_per_screen || '3',
        llm_temp_script: parseFloat(settings.llm_temp_script ?? 0.7),
        llm_temp_metadata: parseFloat(settings.llm_temp_metadata ?? 0.7),
        llm_temp_keywords: parseFloat(settings.llm_temp_keywords ?? 0.7),
        voice_speed: parseFloat(settings.voice_speed ?? 1.0),
        voice_volume: parseFloat(settings.voice_volume ?? 1.0),
        music_volume: parseFloat(settings.music_volume ?? 0.15),
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
          <p className="text-muted-foreground mt-1">Configure models, API keys, Whisper transcription, FFmpeg render settings, and AI generation defaults.</p>
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

      {loadError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-400">
          <strong>Failed to load settings:</strong> {loadError}
          <br />
          <span className="opacity-70">LLM profiles and other settings could not be fetched. Ensure the server is running and refresh.</span>
        </div>
      )}

      <div className="flex-1 md:overflow-y-auto pr-2 space-y-6 pb-6">
        <LLMProfilesSection
          profiles={settings.llm_profiles || []}
          activeProfileId={settings.active_llm_profile_id}
          onChange={handleProfileChange}
          onDelete={handleDeleteProfile}
          onSetActive={handleSetActiveProfile}
          onFetchModels={handleFetchModels}
          availableModels={availableModels}
          isFetchingModels={isFetchingModels}
          onAddProfile={handleAddProfile}
        />

        <AIGenerationSection
          settings={settings}
          onChange={handleChange}
        />

        <ThirdPartySection
          settings={settings}
          onChange={handleChange}
          onTikTokLogin={async () => {
            try {
              const res = await api.loginTikTok();
              alert(res.message || "Browser opened! Please log in.");
            } catch (e) {
              alert("Error: " + e.message);
            }
          }}
        />

        <WhisperSection
          settings={settings}
          onChange={handleChange}
        />

        <FFmpegSection
          settings={settings}
          onChange={handleChange}
        />

        <AudioDefaultsSection
          settings={settings}
          onChange={handleChange}
        />

        <SystemPerformanceSection
          settings={settings}
          onChange={handleChange}
          notificationStatus={notificationStatus}
          onRequestNotification={requestNotificationPermission}
        />
      </div>
    </div>
  )
}
