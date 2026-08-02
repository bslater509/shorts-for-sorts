import { useState, useEffect, useRef } from 'react'

import { BottomSheet } from '@/components/ui/bottom-sheet'
import { ChevronUp, Settings2, SlidersHorizontal } from 'lucide-react'
import { Layers, ChevronDown, Check, Play, Loader2, AlertOctagon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { useAppStore } from '@/store/useAppStore'
import { toast } from 'sonner'
import * as api from '@/lib/api'

// Subtitle animation styles supported by the generator (used for the
// sub_animation_style batch override).
const ANIMATION_STYLES = [
  { value: 'tiktok_pop', label: 'TikTok Pop' },
  { value: 'bouncy_bounce', label: 'Bouncy Bounce' },
  { value: 'cinematic_zoom', label: 'Cinematic Zoom' },
  { value: 'glow_shake', label: 'Glow Shake' },
  { value: 'neon_flicker', label: 'Neon Flicker' },
  { value: 'pulse_grow', label: 'Pulse Grow' },
  { value: 'fade_in_slide', label: 'Fade In Slide' },
  { value: 'karaoke_sweep', label: 'Karaoke Sweep' },
  { value: 'typewriter_swipe', label: 'Typewriter Swipe' },
]

// Common values for the temperature / concurrency overrides.
const TEMP_OPTIONS = ['0.0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1.0', '1.1', '1.2', '1.3', '1.4', '1.5']
const WORKER_OPTIONS = ['1', '2', '3', '4', '6', '8']
const LLM_WORKER_OPTIONS = ['1', '2', '3', '4', '6', '8', '10']

// Base classes for the compact selects used inside popover/sheet settings.
const SELECT_BASE = 'bg-background border border-border rounded-md px-2 py-1 text-xs h-auto min-h-0'

const Row = ({ label, hint, children }) => (
  <div className="flex items-center justify-between gap-2">
    <div className="min-w-0">
      <Label className="text-xs md:text-[10px] font-medium text-muted-foreground leading-tight">{label}</Label>
      {hint && <p className="text-[9px] md:text-[8px] text-muted-foreground/50 mt-0.5">{hint}</p>}
    </div>
    {children}
  </div>
)

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

  const [mobileOptionsOpen, setMobileOptionsOpen] = useState(false)

  const [emojiPopoverOpen, setEmojiPopoverOpen] = useState(false)
  const emojiRef = useRef(null)

  // Advanced generation options — bound to appState so they persist across
  // sessions (saved server-side via saveCurrentState -> POST /api/state).
  const batchLayout = useAppStore((s) => s.appState?.batch_layout ?? 'Random')
  const batchVoiceId = useAppStore((s) => s.appState?.batch_voice_id ?? 'Random')
  const batchSubAnimationStyle = useAppStore((s) => s.appState?.batch_sub_animation_style ?? 'Random')
  const batchWordsPerScreen = useAppStore((s) => s.appState?.batch_words_per_screen ?? 'Default')
  const batchSingleWordMode = useAppStore((s) => s.appState?.batch_single_word_mode ?? false)
  const batchBgMusicPath = useAppStore((s) => s.appState?.batch_bg_music_path ?? 'Random')
  const batchScriptTemp = useAppStore((s) => s.appState?.batch_script_temp ?? s.settings?.llm_temp_script ?? 0.7)
  const batchMetaTemp = useAppStore((s) => s.appState?.batch_meta_temp ?? s.settings?.llm_temp_metadata ?? 0.7)
  const batchMaxWorkers = useAppStore((s) => s.appState?.batch_max_workers ?? s.settings?.max_workers ?? 1)
  const batchLlmMaxWorkers = useAppStore((s) => s.appState?.batch_llm_max_workers ?? s.settings?.llm_max_workers ?? 5)

  const batch = {
    layout: batchLayout,
    voiceId: batchVoiceId,
    subAnimationStyle: batchSubAnimationStyle,
    wordsPerScreen: batchWordsPerScreen,
    singleWordMode: batchSingleWordMode,
    bgMusicPath: batchBgMusicPath,
    scriptTemp: batchScriptTemp,
    metaTemp: batchMetaTemp,
    maxWorkers: batchMaxWorkers,
    llmMaxWorkers: batchLlmMaxWorkers,
  }
  const voices = useAppStore((s) => s.voices || [])

  const [advancedPopoverOpen, setAdvancedPopoverOpen] = useState(false)
  const advancedRef = useRef(null)
  const [musicFiles, setMusicFiles] = useState([])

  // Fetch available music tracks for the background-music override.
  useEffect(() => {
    api.fetchMusic()
      .then((data) => setMusicFiles(Array.isArray(data) ? data : []))
      .catch(() => { /* music listing is best-effort */ })
  }, [])

  // Close the desktop Advanced popover when clicking outside. Mobile uses a
  // BottomSheet instead, which manages its own backdrop dismissal.
  useEffect(() => {
    const handleClick = (e) => {
      if (typeof window !== 'undefined' && window.innerWidth < 768) return
      if (advancedRef.current && !advancedRef.current.contains(e.target)) {
        setAdvancedPopoverOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Persist an advanced option to appState immediately.
  const setBatchOption = (key, value) => {
    updateAppState({ [key]: value })
    saveCurrentState()
  }

  const hasAdvancedOverrides =
    batch.layout !== 'Random' ||
    batch.voiceId !== 'Random' ||
    batch.subAnimationStyle !== 'Random' ||
    batch.wordsPerScreen !== 'Default' ||
    batch.singleWordMode ||
    batch.bgMusicPath !== 'Random'

  const musicValues = musicFiles.map((m) => `music/${m.filename}`)
  // Show the configured track if one is set (the fallback SelectItem below
  // keeps the trigger populated even when that file was deleted); otherwise
  // fall back to "Random".
  const currentMusicValue = batch.bgMusicPath && batch.bgMusicPath !== 'Random'
    ? batch.bgMusicPath
    : 'Random'

  // Ensure a select always has an item matching the current value so Radix
  // doesn't render an empty trigger (e.g. temps not in the presets list).
  const ensureOption = (current, options) => {
    const str = String(current)
    return options.includes(str) ? options : [str, ...options]
  }

  const renderPromptSelector = () => (
    <>
      <div className="p-1.5 border-b border-border bg-secondary/30 flex justify-between items-center text-[10px]">
        <span className="font-semibold text-muted-foreground hidden md:inline">Select Prompts</span>
        <div className="space-x-2 md:ml-auto">
          <Button variant="ghost" onClick={() => setSelectedPrompts(Object.keys(availablePrompts))} className="text-blue-500 hover:underline h-auto p-0 text-sm md:text-[10px]">Select All</Button>
          <span className="text-muted-foreground"> | </span>
          <Button variant="ghost" onClick={() => setSelectedPrompts([])} className="text-muted-foreground hover:underline h-auto p-0 text-sm md:text-[10px]">Clear</Button>
        </div>
      </div>
      <div className="overflow-y-auto p-1 flex-1">
        {Object.keys(availablePrompts).length === 0 && <div className="p-2 text-sm md:text-xs text-muted-foreground text-center">No prompts found</div>}
        {Object.keys(availablePrompts).map(key => (
          <Label key={key} className="flex items-start gap-3 md:gap-2 p-2.5 md:p-1.5 hover:bg-secondary/50 rounded cursor-pointer transition-colors">
            <div className="mt-0.5 flex-shrink-0 flex items-center justify-center w-4 h-4 md:w-3.5 md:h-3.5 rounded border border-border bg-background">
              {selectedPrompts.includes(key) && <Check size={12} className="text-blue-500" />}
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
              <span className="text-sm md:text-xs font-medium leading-none">{key}</span>
              <span className="text-xs md:text-[10px] text-muted-foreground mt-1 md:mt-0.5 line-clamp-2" title={availablePrompts[key]}>{availablePrompts[key]}</span>
            </div>
          </Label>
        ))}
      </div>
    </>
  )

  const renderEmojiSettings = () => (
    <>
      <div className="p-3 md:p-2 border-b border-border bg-secondary/30">
        <p className="text-xs md:text-[10px] font-semibold text-muted-foreground mb-2 md:mb-1.5">Emoji Settings</p>
        <Label className="flex items-center justify-between cursor-pointer hover:bg-secondary/50 rounded px-2 py-2 md:px-1.5 md:py-1 transition-colors">
          <span className="text-sm md:text-[11px] text-foreground font-medium">Enable Emojis</span>
          <input
            type="checkbox"
            checked={enableEmojis}
            onChange={() => !inProgress && setEnableEmojis(!enableEmojis)}
            disabled={inProgress}
            className="sr-only"
          />
          <span className={`w-10 md:w-8 h-5 md:h-4 rounded-full transition-colors ${enableEmojis ? 'bg-yellow-500' : 'bg-muted'} relative`}>
            <span className={`absolute top-0.5 w-4 md:w-3 h-4 md:h-3 rounded-full bg-white transition-transform ${enableEmojis ? 'translate-x-5 md:translate-x-4' : 'translate-x-0.5 md:translate-x-0.5'}`} />
          </span>
        </Label>
      </div>
      <div className="p-3 md:p-2 space-y-3 md:space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs md:text-[10px] font-medium text-muted-foreground">Animation</Label>
          <Button
            variant="outline"
            onClick={() => !inProgress && setEnableEmojiAnimation(!enableEmojiAnimation)}
            disabled={inProgress || !enableEmojis}
            className={`text-xs md:text-[10px] px-2.5 md:px-1.5 py-1.5 md:py-0.5 rounded-md md:rounded font-medium border h-auto transition-all duration-200 ${
              enableEmojiAnimation
                ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                : 'bg-muted/50 text-muted-foreground/60 border-border/30'
            } disabled:opacity-50`}
          >
            {enableEmojiAnimation ? 'On' : 'Off'}
          </Button>
        </div>
        <div className="flex items-center justify-between">
          <Label className="text-xs md:text-[10px] font-medium text-muted-foreground">Scale</Label>
          <Select value={String(emojiScaleFactor)} onValueChange={(v) => { updateAppState({ emoji_scale_factor: parseFloat(v) }); saveCurrentState() }} disabled={!enableEmojis}>
            <SelectTrigger className="w-16 md:w-14 bg-background border border-border rounded-md px-2 md:px-1 py-1 md:py-0.5 text-xs md:text-[10px] text-center h-auto min-h-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[0.5,1.0,1.5,2.0,2.5,3.0].map(n => (
                <SelectItem key={n} value={String(n)}>{n}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between">
          <Label className="text-xs md:text-[10px] font-medium text-muted-foreground">Hold Duration</Label>
          <Select value={String(emojiHoldDuration)} onValueChange={(v) => { updateAppState({ emoji_hold_duration: parseFloat(v) }); saveCurrentState() }} disabled={!enableEmojis}>
            <SelectTrigger className="w-16 md:w-14 bg-background border border-border rounded-md px-2 md:px-1 py-1 md:py-0.5 text-xs md:text-[10px] text-center h-auto min-h-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[0,0.5,1.0,1.5,2.0].map(n => (
                <SelectItem key={n} value={String(n)}>{n}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between">
          <Label className="text-xs md:text-[10px] font-medium text-muted-foreground">Max / Word</Label>
          <Select value={String(emojiThrowMaxCount)} onValueChange={(v) => { updateAppState({ emoji_throw_max_count: parseInt(v) }); saveCurrentState() }} disabled={!enableEmojis}>
            <SelectTrigger className="w-16 md:w-14 bg-background border border-border rounded-md px-2 md:px-1 py-1 md:py-0.5 text-xs md:text-[10px] text-center h-auto min-h-0">
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
    </>
  )

  const renderAdvancedSettings = () => {
    const rowSelectCls = (width) => `${SELECT_BASE} ${width} text-left`

    return (
      <>
        <div className="p-3 md:p-2 border-b border-border bg-secondary/30 flex items-center gap-1.5">
          <SlidersHorizontal size={12} className="text-violet-400" />
          <p className="text-xs md:text-[10px] font-semibold text-muted-foreground">Advanced Generation Options</p>
          <span className="ml-auto text-[10px] md:text-[9px] text-muted-foreground/50 font-medium hidden md:inline">per-job overrides</span>
        </div>
        <div className="p-3 md:p-2 space-y-3 md:space-y-2 max-h-[70vh] md:max-h-96 overflow-y-auto">
          {/* Layout */}
          <Row label="Layout" hint="Split vs. full-screen backgrounds">
            <Select value={String(batch.layout)} onValueChange={(v) => setBatchOption('batch_layout', v)} disabled={inProgress}>
              <SelectTrigger className={rowSelectCls('w-32')}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Random">Random</SelectItem>
                <SelectItem value="Split-Screen">Split-Screen</SelectItem>
                <SelectItem value="Full Screen">Full Screen</SelectItem>
              </SelectContent>
            </Select>
          </Row>

          {/* Voice */}
          <Row label="Voice" hint={batch.voiceId !== 'Random' ? batch.voiceId : 'Random voice per job'}>
            <Select value={String(batch.voiceId)} onValueChange={(v) => setBatchOption('batch_voice_id', v)} disabled={inProgress}>
              <SelectTrigger className={rowSelectCls('w-44')}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Random">Random</SelectItem>
                {voices.map((v) => (
                  <SelectItem key={v.value} value={v.value}>{v.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Row>

          {/* Subtitle animation style */}
          <Row label="Sub Animation" hint="Caption animation style">
            <Select value={String(batch.subAnimationStyle)} onValueChange={(v) => setBatchOption('batch_sub_animation_style', v)} disabled={inProgress}>
              <SelectTrigger className={rowSelectCls('w-40')}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Random">Random</SelectItem>
                {ANIMATION_STYLES.map((a) => (
                  <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Row>

          {/* Words per screen */}
          <Row label="Words / Screen" hint="Caption phrasing">
            <Select value={String(batch.wordsPerScreen)} onValueChange={(v) => setBatchOption('batch_words_per_screen', v)} disabled={inProgress}>
              <SelectTrigger className={rowSelectCls('w-28')}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Default">Default</SelectItem>
                <SelectItem value="1">1 word</SelectItem>
                <SelectItem value="3">3 words</SelectItem>
                <SelectItem value="sentence">Sentence</SelectItem>
                <SelectItem value="random">Random</SelectItem>
              </SelectContent>
            </Select>
          </Row>

          {/* Single word mode */}
          <Row label="Single Word Mode" hint="One word on screen at a time">
            <Switch
              checked={batch.singleWordMode}
              onCheckedChange={(v) => setBatchOption('batch_single_word_mode', v)}
              disabled={inProgress}
              className="data-[state=checked]:bg-violet-500"
            />
          </Row>

          {/* Background music */}
          <Row label="Music" hint={batch.bgMusicPath !== 'Random' ? String(batch.bgMusicPath).replace(/^music\//, '') : 'Random track per job'}>
            <Select value={String(currentMusicValue)} onValueChange={(v) => setBatchOption('batch_bg_music_path', v)} disabled={inProgress}>
              <SelectTrigger className={rowSelectCls('w-44')}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Random">Random</SelectItem>
                {musicFiles.map((m) => (
                  <SelectItem key={m.filename} value={`music/${m.filename}`} className="truncate">{m.filename}</SelectItem>
                ))}
                {!musicValues.includes(batch.bgMusicPath) && batch.bgMusicPath !== 'Random' && (
                  <SelectItem value={batch.bgMusicPath} className="truncate">{String(batch.bgMusicPath).replace(/^music\//, '')}</SelectItem>
                )}
                {musicFiles.length === 0 && (
                  <SelectItem value="__empty__" disabled>No music tracks found</SelectItem>
                )}
              </SelectContent>
            </Select>
          </Row>

          {/* Temperatures */}
          <div className="border-t border-border/40 pt-2.5 md:pt-2 space-y-3 md:space-y-2">
            <Row label="Script Temp" hint="LLM creativity (higher = more varied)">
              <Select value={String(batch.scriptTemp)} onValueChange={(v) => setBatchOption('batch_script_temp', parseFloat(v))} disabled={inProgress}>
                <SelectTrigger className={rowSelectCls('w-20')}><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ensureOption(batch.scriptTemp, TEMP_OPTIONS).map((t) => (
                    <SelectItem key={t} value={String(t)}>{String(t)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Row>
            <Row label="Meta Temp" hint="Title & keyword generation">
              <Select value={String(batch.metaTemp)} onValueChange={(v) => setBatchOption('batch_meta_temp', parseFloat(v))} disabled={inProgress}>
                <SelectTrigger className={rowSelectCls('w-20')}><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ensureOption(batch.metaTemp, TEMP_OPTIONS).map((t) => (
                    <SelectItem key={t} value={String(t)}>{String(t)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Row>
          </div>

          {/* Concurrency */}
          <div className="border-t border-border/40 pt-2.5 md:pt-2 space-y-3 md:space-y-2">
            <Row label="Render Workers" hint="Parallel video renders per job">
              <Select value={String(batch.maxWorkers)} onValueChange={(v) => setBatchOption('batch_max_workers', parseInt(v, 10))} disabled={inProgress}>
                <SelectTrigger className={rowSelectCls('w-20')}><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ensureOption(batch.maxWorkers, WORKER_OPTIONS).map((w) => (
                    <SelectItem key={w} value={String(w)}>{w}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Row>
            <Row label="LLM Workers" hint="Parallel script generation calls">
              <Select value={String(batch.llmMaxWorkers)} onValueChange={(v) => setBatchOption('batch_llm_max_workers', parseInt(v, 10))} disabled={inProgress}>
                <SelectTrigger className={rowSelectCls('w-20')}><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ensureOption(batch.llmMaxWorkers, LLM_WORKER_OPTIONS).map((w) => (
                    <SelectItem key={w} value={String(w)}>{w}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Row>
          </div>
        </div>
      </>
    )
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

      {/* --- DESKTOP TOOLBAR --- */}
      <div className="hidden md:flex items-center gap-1.5 bg-secondary/50 border border-border rounded-xl p-1.5 shrink-0 shadow-sm flex-wrap">
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
            <div className="absolute top-full mt-1 left-0 w-72 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-72">
              {renderPromptSelector()}
            </div>
          )}
        </div>

        <div className="relative" ref={emojiRef}>
          <Button
            variant="outline"
            onClick={() => setEmojiPopoverOpen(!emojiPopoverOpen)}
            disabled={inProgress}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border h-auto ${
              enableEmojis
                ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                : 'bg-muted/50 text-muted-foreground/60 border-border/30'
            } disabled:opacity-50`}
          >
            {enableEmojis ? '😊 Emoji' : '🚫 No Emoji'}
          </Button>

          {emojiPopoverOpen && (
            <div
              className="absolute top-full mt-1 left-1/2 -translate-x-1/2 w-64 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col animate-in fade-in slide-in-from-top-2 zoom-in-95 duration-150"
              onClick={e => e.stopPropagation()}
            >
              {renderEmojiSettings()}
            </div>
          )}
        </div>

        {/* Advanced Generation Options */}
        <div className="relative" ref={advancedRef}>
          <Button
            variant="outline"
            onClick={() => setAdvancedPopoverOpen(!advancedPopoverOpen)}
            disabled={inProgress}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border h-auto transition-all duration-200 ${
              hasAdvancedOverrides
                ? 'bg-violet-500/10 text-violet-400 border-violet-500/20'
                : 'bg-muted/50 text-muted-foreground/60 border-border/30'
            } disabled:opacity-50`}
          >
            <SlidersHorizontal size={10} />
            Advanced
            {hasAdvancedOverrides && <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />}
          </Button>

          {advancedPopoverOpen && (
            <div
              className="absolute top-full mt-1 left-1/2 -translate-x-1/2 w-80 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col animate-in fade-in slide-in-from-top-2 zoom-in-95 duration-150"
              onClick={e => e.stopPropagation()}
            >
              {renderAdvancedSettings()}
            </div>
          )}
        </div>

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

      {/* --- MOBILE TOOLBAR --- */}
      <div className="flex md:hidden flex-col gap-2 w-full mt-2">
        <div className="grid grid-cols-2 gap-2">
          {/* Qty Tile */}
          <div className="bg-secondary/50 border border-border rounded-xl p-2 flex items-center justify-between shadow-sm min-h-[44px]">
            <Label className="text-[11px] font-medium whitespace-nowrap">Qty</Label>
            <Select value={String(numShorts)} onValueChange={(v) => { updateAppState({ batch_num_shorts: parseInt(v) }); saveCurrentState() }} disabled={inProgress}>
              <SelectTrigger className="w-16 bg-background border border-border rounded-md px-2 py-1 text-xs text-center min-h-0 h-auto" disabled={inProgress}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1,2,3,4,5,10,15,20,25,30,40,50].map(n => (
                  <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          {/* Prompts Tile */}
          <Button
            variant="outline"
            onClick={() => setShowPromptDropdown(true)}
            disabled={inProgress}
            className="w-full flex items-center justify-between gap-1 bg-secondary/50 border border-border rounded-xl p-2 text-xs font-medium hover:bg-secondary/70 disabled:opacity-50 h-auto min-h-[44px] shadow-sm"
          >
            <span className="truncate">Prompts ({selectedPrompts.length})</span>
            <ChevronDown size={14} className="opacity-50 flex-shrink-0" />
          </Button>
        </div>

        {/* Options Accordion */}
        <div className="bg-secondary/30 border border-border rounded-xl shadow-sm overflow-hidden transition-all duration-300">
          <button
            onClick={() => setMobileOptionsOpen(!mobileOptionsOpen)}
            className="w-full flex items-center justify-between p-3 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="flex items-center gap-2"><Settings2 size={14} /> Advanced Options</span>
            {mobileOptionsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          
          {mobileOptionsOpen && (
            <div className="p-2 border-t border-border/50 grid grid-cols-2 gap-2 bg-secondary/10">
              <Button
                variant="outline"
                onClick={() => setEmojiPopoverOpen(true)}
                disabled={inProgress}
                className={`w-full flex items-center justify-between px-2 py-2 rounded-lg text-xs font-medium border h-auto min-h-[44px] shadow-sm ${
                  enableEmojis
                    ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                    : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                } disabled:opacity-50`}
              >
                <span className="truncate">{enableEmojis ? '😊 Emoji On' : '🚫 No Emoji'}</span>
                <Settings2 size={12} className="opacity-50 flex-shrink-0" />
              </Button>

              <Button
                variant="outline"
                onClick={handleFailureModeToggle}
                disabled={inProgress}
                className={`w-full flex items-center justify-between gap-1 px-2 py-2 rounded-lg text-xs font-medium border h-auto min-h-[44px] shadow-sm transition-all duration-200 ${
                  failureMode === 'stop_on_failure'
                    ? 'bg-red-500/10 text-red-400 border-red-500/20'
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                } disabled:opacity-50`}
              >
                <span className="flex items-center gap-1.5 truncate">
                  <AlertOctagon size={12} className="flex-shrink-0" />
                  <span className="truncate">{failureMode === 'stop_on_failure' ? 'Stop on fail' : 'Cont. on fail'}</span>
                </span>
              </Button>
              
              <Button
                variant="outline"
                onClick={() => setAdvancedPopoverOpen(true)}
                disabled={inProgress}
                className={`w-full flex items-center justify-between col-span-2 gap-1 px-3 py-2 rounded-lg text-xs font-medium border h-auto min-h-[44px] shadow-sm transition-all duration-200 ${
                  hasAdvancedOverrides
                    ? 'bg-violet-500/10 text-violet-400 border-violet-500/20'
                    : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                } disabled:opacity-50`}
              >
                <span className="flex items-center gap-1.5 truncate">
                  <SlidersHorizontal size={14} className="flex-shrink-0" />
                  <span className="truncate">Advanced Generation Options</span>
                </span>
                {hasAdvancedOverrides ? (
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 flex-shrink-0 animate-pulse" />
                ) : (
                  <ChevronDown size={14} className="opacity-50 flex-shrink-0" />
                )}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Bottom Sheets */}
      <BottomSheet 
        isOpen={showPromptDropdown && typeof window !== 'undefined' && window.innerWidth < 768} 
        onClose={() => setShowPromptDropdown(false)} 
        title={`Select Prompts (${selectedPrompts.length})`}
      >
        <div className="flex flex-col gap-1">
           {renderPromptSelector()}
        </div>
      </BottomSheet>
      
      <BottomSheet 
        isOpen={emojiPopoverOpen && typeof window !== 'undefined' && window.innerWidth < 768} 
        onClose={() => setEmojiPopoverOpen(false)} 
        title="Emoji Settings"
      >
        {renderEmojiSettings()}
      </BottomSheet>

      <BottomSheet 
        isOpen={advancedPopoverOpen && typeof window !== 'undefined' && window.innerWidth < 768} 
        onClose={() => setAdvancedPopoverOpen(false)} 
        title="Advanced Generation Options"
      >
        {renderAdvancedSettings()}
      </BottomSheet>

    </header>
  )

}

export default BatchHeader
