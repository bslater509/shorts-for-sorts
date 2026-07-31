import { useState, useEffect, useRef } from 'react'
import { Layers, ChevronDown, Check, Play, Loader2, FolderOpen, Save, Trash2, AlertOctagon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useAppStore } from '@/store/useAppStore'
import { toast } from 'sonner'
import * as api from '@/lib/api'

const BatchHeader = ({
  availablePrompts,
  selectedPrompts,
  setSelectedPrompts,
  showPromptDropdown,
  setShowPromptDropdown,
  numShorts,
  inProgress,
  updateAppState,
  saveCurrentState,
  enableEmojis,
  setEnableEmojis,
  enableEmojiAnimation,
  setEnableEmojiAnimation,
  emojiScaleFactor,
  emojiHoldDuration,
  emojiThrowMaxCount,
  handleStart,
  isStarting
}) => {
  const failureMode = useAppStore((s) => s.settings?.batch_failure_mode)
  const updateSettings = useAppStore((s) => s.updateSettings)

  // Failure mode toggle
  const handleFailureModeToggle = async () => {
    const newMode = failureMode === 'stop_on_failure' ? 'continue_on_failure' : 'stop_on_failure'
    try {
      await api.saveSettings({ batch_failure_mode: newMode })
      updateSettings({ batch_failure_mode: newMode })
    } catch (err) {
      toast.error("Failed to update failure mode", { description: err.message })
    }
  }

  // Batch profiles
  const [profiles, setProfiles] = useState([])
  const [profilesOpen, setProfilesOpen] = useState(false)
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [profileNameInput, setProfileNameInput] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profilesLoading, setProfilesLoading] = useState(false)
  const profilesRef = useRef(null)

  // Close profiles dropdown on click outside
  useEffect(() => {
    const handleClick = (e) => {
      if (profilesRef.current && !profilesRef.current.contains(e.target)) {
        setProfilesOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const fetchProfiles = async () => {
    setProfilesLoading(true)
    try {
      const data = await api.getBatchProfiles()
      setProfiles(data?.profiles || [])
    } catch (err) {
      console.debug("Failed to fetch batch profiles", err)
    } finally {
      setProfilesLoading(false)
    }
  }

  const handleLoadProfile = async (profileName) => {
    try {
      const data = await api.getBatchProfiles()
      const profile = (data?.profiles || []).find(p => p.name === profileName)
      if (profile?.config) {
        updateAppState(profile.config)
        saveCurrentState()
        setSelectedProfile(profileName)
        toast.success(`Profile "${profileName}" loaded`)
      }
    } catch (err) {
      toast.error("Failed to load profile", { description: err.message })
    }
  }

  const handleSaveProfile = async () => {
    const name = profileNameInput.trim()
    if (!name) {
      toast.error("Profile name required")
      return
    }
    setSavingProfile(true)
    try {
      const config = {
        batch_num_shorts: numShorts,
        enable_emojis: enableEmojis,
        enable_emoji_animation: enableEmojiAnimation,
        emoji_scale_factor: emojiScaleFactor,
        emoji_hold_duration: emojiHoldDuration,
        emoji_throw_max_count: emojiThrowMaxCount,
        selected_prompts: selectedPrompts
      }
      await api.saveBatchProfile(name, config)
      toast.success(`Profile "${name}" saved`)
      setProfileNameInput('')
      fetchProfiles()
    } catch (err) {
      toast.error("Failed to save profile", { description: err.message })
    } finally {
      setSavingProfile(false)
    }
  }

  const handleDeleteProfile = async (name) => {
    if (!window.confirm(`Delete profile "${name}"?`)) return
    try {
      await api.deleteBatchProfile(name)
      toast.success(`Profile "${name}" deleted`)
      if (selectedProfile === name) setSelectedProfile(null)
      fetchProfiles()
    } catch (err) {
      toast.error("Failed to delete profile", { description: err.message })
    }
  }

  return (
    <header className="shrink-0 flex flex-col sm:flex-row items-start sm:justify-between gap-3">
      <div className="flex items-start gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight flex items-center gap-2">
            <Layers className="text-blue-500" size={22} />
            Batch Generator
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground mt-0.5">Generate multiple videos autonomously.</p>
        </div>
      </div>

      <div className="flex items-center gap-1.5 bg-secondary/50 border border-border rounded-xl p-1.5 shrink-0 shadow-sm flex-wrap">
        <div className="flex items-center gap-1 px-1.5">
          <Label className="text-[11px] font-medium whitespace-nowrap">Qty</Label>
          <Select value={String(numShorts)} onValueChange={(v) => { updateAppState({ batch_num_shorts: parseInt(v) }); saveCurrentState() }} disabled={inProgress}>
            <SelectTrigger className="w-14 bg-background border border-border rounded-md px-1 py-0.5 text-xs text-center" disabled={inProgress}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[1,2,3,4,5,10,15,20,25,30,40,50].map(n => (
                <SelectItem key={n} value={String(n)}>{n}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="relative">
          <Button
            variant="outline"
            onClick={() => setShowPromptDropdown(!showPromptDropdown)}
            disabled={inProgress}
            className="flex items-center gap-1 bg-background border border-border rounded-md px-2 py-0.5 text-xs font-medium hover:bg-secondary/50 disabled:opacity-50 h-auto"
          >
            Prompts ({selectedPrompts.length}) <ChevronDown size={11} />
          </Button>
          {showPromptDropdown && !inProgress && (
            <div className="absolute top-full mt-1 right-0 md:right-auto md:left-0 w-72 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-72">
              <div className="p-1.5 border-b border-border bg-secondary/30 flex justify-between items-center text-[10px]">
                <span className="font-semibold text-muted-foreground">Select Prompts</span>
                <div className="space-x-2">
                  <Button variant="ghost" onClick={() => setSelectedPrompts(Object.keys(availablePrompts))} className="text-blue-500 hover:underline h-auto p-0">All</Button>
                  <Button variant="ghost" onClick={() => setSelectedPrompts([])} className="text-muted-foreground hover:underline h-auto p-0">None</Button>
                </div>
              </div>
              <div className="overflow-y-auto p-1">
                {Object.keys(availablePrompts).length === 0 && <div className="p-2 text-xs text-muted-foreground text-center">No prompts found</div>}
                {Object.keys(availablePrompts).map(key => (
                  <Label key={key} className="flex items-start gap-2 p-1.5 hover:bg-secondary/50 rounded cursor-pointer">
                    <div className="mt-0.5 flex-shrink-0 flex items-center justify-center w-3.5 h-3.5 rounded border border-border bg-background">
                      {selectedPrompts.includes(key) && <Check size={10} className="text-blue-500" />}
                    </div>
                    <input
                      type="checkbox"
                      className="hidden"
                      checked={selectedPrompts.includes(key)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedPrompts(prev => [...prev, key])
                        else setSelectedPrompts(prev => prev.filter(p => p !== key))
                      }}
                    />
                    <div className="flex flex-col">
                      <span className="text-xs font-medium leading-none">{key}</span>
                      <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2" title={availablePrompts[key]}>{availablePrompts[key]}</span>
                    </div>
                    </Label>
                ))}
              </div>
            </div>
          )}
        </div>

        <Button
          variant="outline"
          onClick={() => setEnableEmojis(!enableEmojis)}
          disabled={inProgress}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border h-auto ${
            enableEmojis
              ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
              : 'bg-muted/50 text-muted-foreground/60 border-border/30'
          } disabled:opacity-50`}
        >
          {enableEmojis ? '😊 Emoji' : '🚫 No Emoji'}
        </Button>

        {enableEmojis && (
          <div
            className="flex items-center gap-1.5 bg-secondary/30 border border-border rounded-lg p-1.5 animate-in fade-in slide-in-from-top-2 zoom-in-95 duration-200 flex-wrap origin-top-right"
          >
            <div className="flex items-center gap-1">
              <Label className="text-[10px] md:text-[9px] font-medium text-muted-foreground whitespace-nowrap">Anim</Label>
              <Button
                variant="outline"
                onClick={() => setEnableEmojiAnimation(!enableEmojiAnimation)}
                className={`text-[10px] px-1.5 py-1 md:py-0.5 rounded font-medium border h-auto transition-all duration-200 ${
                  enableEmojiAnimation
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/20 shadow-[0_0_6px_rgba(59,130,246,0.15)]'
                    : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                }`}
              >
                {enableEmojiAnimation ? 'On' : 'Off'}
              </Button>
            </div>
            <div className="w-px h-4 bg-border/50" />
            <div className="flex items-center gap-1">
              <Label className="text-[10px] md:text-[9px] font-medium text-muted-foreground whitespace-nowrap">Scale</Label>
              <Select value={String(emojiScaleFactor)} onValueChange={(v) => { updateAppState({ emoji_scale_factor: parseFloat(v) }); saveCurrentState() }}>
                <SelectTrigger className="w-12 bg-background border border-border rounded-md px-1 py-0.5 text-[10px] text-center h-auto">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[0.5,1.0,1.5,2.0,2.5,3.0].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-px h-4 bg-border/50" />
            <div className="flex items-center gap-1">
              <Label className="text-[10px] md:text-[9px] font-medium text-muted-foreground whitespace-nowrap">Hold</Label>
              <Select value={String(emojiHoldDuration)} onValueChange={(v) => { updateAppState({ emoji_hold_duration: parseFloat(v) }); saveCurrentState() }}>
                <SelectTrigger className="w-12 bg-background border border-border rounded-md px-1 py-0.5 text-[10px] text-center h-auto">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[0,0.5,1.0,1.5,2.0].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-px h-4 bg-border/50" />
            <div className="flex items-center gap-1">
              <Label className="text-[10px] md:text-[9px] font-medium text-muted-foreground whitespace-nowrap">Max/Word</Label>
              <Select value={String(emojiThrowMaxCount)} onValueChange={(v) => { updateAppState({ emoji_throw_max_count: parseInt(v) }); saveCurrentState() }}>
                <SelectTrigger className="w-12 bg-background border border-border rounded-md px-1 py-0.5 text-[10px] text-center h-auto">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1,3,5,10,15,20].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {/* Failure Mode Toggle */}
        <div className="w-px h-4 bg-border/50" />
        <Button
          variant="outline"
          onClick={handleFailureModeToggle}
          disabled={inProgress}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium border h-auto transition-all duration-200 ${
            failureMode === 'stop_on_failure'
              ? 'bg-red-500/10 text-red-400 border-red-500/20'
              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
          } disabled:opacity-50`}
          title={failureMode === 'stop_on_failure' ? 'Stop on failure' : 'Continue on failure'}
        >
          <AlertOctagon size={10} />
          {failureMode === 'stop_on_failure' ? 'Stop' : 'Continue'}
        </Button>

        {/* Batch Profiles */}
        <div className="w-px h-4 bg-border/50" />
        <div className="relative" ref={profilesRef}>
          <Button
            variant="outline"
            onClick={() => {
              setProfilesOpen(!profilesOpen)
              if (!profilesOpen) fetchProfiles()
            }}
            disabled={inProgress}
            className="flex items-center gap-1 bg-background border border-border rounded-md px-2 py-0.5 text-[10px] font-medium hover:bg-secondary/50 disabled:opacity-50 h-auto"
          >
            <FolderOpen size={10} />
            {selectedProfile || 'Profiles'} <ChevronDown size={10} />
          </Button>

          {profilesOpen && !inProgress && (
            <div className="absolute top-full mt-1 right-0 w-64 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-80">
              <div className="p-2 border-b border-border bg-secondary/30">
                <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">Batch Profiles</p>
                {profiles.length > 0 && (
                  <div className="max-h-36 overflow-y-auto space-y-0.5 mb-2">
                    {profiles.map((p) => (
                      <div key={p.name} className="flex items-center justify-between gap-1 rounded hover:bg-secondary/50 px-1.5 py-1">
                        <button
                          onClick={() => { handleLoadProfile(p.name); setProfilesOpen(false) }}
                          className={`text-[11px] text-left flex-1 truncate ${
                            selectedProfile === p.name ? 'text-blue-400 font-semibold' : 'text-foreground'
                          }`}
                        >
                          {p.name}
                        </button>
                        <button
                          onClick={() => handleDeleteProfile(p.name)}
                          className="text-muted-foreground hover:text-red-400 transition-colors p-0.5"
                        >
                          <Trash2 size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {profilesLoading && <p className="text-[10px] text-muted-foreground text-center py-1">Loading...</p>}
              </div>
              <div className="p-2 space-y-1.5">
                <Input
                  value={profileNameInput}
                  onChange={(e) => setProfileNameInput(e.target.value)}
                  placeholder="New profile name..."
                  className="h-7 text-[11px] px-2 py-1"
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSaveProfile() }}
                />
                <Button
                  variant="outline"
                  onClick={handleSaveProfile}
                  disabled={savingProfile || !profileNameInput.trim()}
                  className="w-full text-[10px] h-7 px-2 flex items-center gap-1"
                >
                  {savingProfile ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
                  Save Current Config
                </Button>
              </div>
            </div>
          )}
        </div>

        <Button
          variant="default"
          onClick={handleStart}
          disabled={inProgress || isStarting || selectedPrompts.length === 0}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium text-xs bg-blue-500 hover:bg-blue-600 text-white shadow-md disabled:opacity-50 h-auto transition-all duration-200 ${
            !inProgress && !isStarting && selectedPrompts.length > 0
              ? 'shadow-blue-500/25 hover:shadow-blue-500/40'
              : ''
          }`}
        >
          {isStarting ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} className={!inProgress && selectedPrompts.length > 0 ? 'animate-pulse' : ''} style={{ animationDuration: '2s' }} />}
          {isStarting ? 'Starting...' : 'Start Batch'}
        </Button>
      </div>
    </header>
  )
}

export default BatchHeader
