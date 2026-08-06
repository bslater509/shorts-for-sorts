import { useState, useEffect, useCallback } from 'react'
import {
  CalendarClock, Plus, Pencil, Trash2, Play, Clock, Check, ChevronDown, ChevronUp,
  X, Loader2, SlidersHorizontal, Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/useAppStore'
import { toast } from 'sonner'

// Subtitle animation styles supported by the generator (mirrors BatchHeader).
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

const TEMP_OPTIONS = ['0.0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1.0', '1.1', '1.2', '1.3', '1.4', '1.5']
const WORKER_OPTIONS = ['1', '2', '3', '4', '6', '8']
const LLM_WORKER_OPTIONS = ['1', '2', '3', '4', '6', '8', '10']
const QUANTITY_OPTIONS = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50]

const CADENCE_OPTIONS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'interval', label: 'Interval' },
]

const DAY_SHORT = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

// Last-run status badge mapping.
const STATUS_STYLES = {
  running: { label: 'Running', cls: 'bg-blue-500/10 text-blue-400 border-blue-500/30', dot: 'bg-blue-500 animate-pulse' },
  completed: { label: 'Completed', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-500' },
  done: { label: 'Completed', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-500' },
  success: { label: 'Completed', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-500' },
  skipped: { label: 'Skipped', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', dot: 'bg-amber-500' },
  failed: { label: 'Failed', cls: 'bg-red-500/10 text-red-400 border-red-500/30', dot: 'bg-red-500' },
  error: { label: 'Failed', cls: 'bg-red-500/10 text-red-400 border-red-500/30', dot: 'bg-red-500' },
}

const statusStyle = (status) => STATUS_STYLES[String(status || '').toLowerCase()] || {
  label: 'Idle', cls: 'bg-muted/50 text-muted-foreground/60 border-border/30', dot: 'bg-muted-foreground',
}

const Row = ({ label, hint, children }) => (
  <div className="flex items-center justify-between gap-2">
    <div className="min-w-0">
      <Label className="text-xs font-medium text-muted-foreground leading-tight">{label}</Label>
      {hint && <p className="text-[10px] text-muted-foreground/50 mt-0.5 truncate" title={hint}>{hint}</p>}
    </div>
    {children}
  </div>
)

const Section = ({ title, children }) => (
  <div className="space-y-3">
    <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{title}</h3>
    {children}
  </div>
)

// ---------------------------------------------------------------------------
// Form mapping helpers
// ---------------------------------------------------------------------------

const createDefaultForm = () => ({
  name: '',
  enabled: true,
  cadence: 'daily',
  times: ['09:00'],
  days: [1, 2, 3, 4, 5],
  interval_hours: 3,
  interval_start: '08:00',
  interval_end: '23:00',
  jitter_minutes: 45,
  stagger_enabled: false,
  stagger_min_minutes: 60,
  stagger_max_minutes: 240,
  post_to_tiktok: true,
  num_shorts: 5,
  prompts: [],
  enable_emojis: true,
  enable_emoji_animation: true,
  emoji_scale_factor: 1.5,
  emoji_hold_duration: 0.5,
  emoji_throw_max_count: 3,
  layout: 'Random',
  voice_id: 'Random',
  sub_animation_style: 'Random',
  words_per_screen: 'Default',
  single_word_mode: false,
  bg_music_path: 'Random',
  script_temp: 0.7,
  meta_temp: 0.7,
  max_workers: 1,
  llm_max_workers: 5,
})

const toForm = (s) => ({
  name: s.name || '',
  enabled: s.enabled !== false,
  cadence: s.cadence || 'daily',
  times: (s.times && s.times.length ? s.times : ['09:00']),
  days: (s.days && s.days.length ? s.days : [1, 2, 3, 4, 5]),
  interval_hours: s.interval_hours || 3,
  interval_start: s.interval_start || '08:00',
  interval_end: s.interval_end || '23:00',
  jitter_minutes: s.jitter_minutes ?? 45,
  stagger_enabled: !!s.stagger_enabled,
  stagger_min_minutes: s.stagger_min_minutes || 60,
  stagger_max_minutes: s.stagger_max_minutes || 240,
  post_to_tiktok: s.post_to_tiktok !== false,
  num_shorts: s.num_shorts || 5,
  prompts: s.prompts || [],
  enable_emojis: s.enable_emojis !== false,
  enable_emoji_animation: s.enable_emoji_animation !== false,
  emoji_scale_factor: s.emoji_scale_factor ?? 1.5,
  emoji_hold_duration: s.emoji_hold_duration ?? 0.5,
  emoji_throw_max_count: s.emoji_throw_max_count ?? 3,
  layout: s.layout ?? 'Random',
  voice_id: s.voice_id ?? 'Random',
  sub_animation_style: s.sub_animation_style ?? 'Random',
  words_per_screen: s.words_per_screen ?? 'Default',
  single_word_mode: s.single_word_mode ?? false,
  bg_music_path: s.bg_music_path ?? 'Random',
  script_temp: s.script_temp ?? 0.7,
  meta_temp: s.meta_temp ?? 0.7,
  max_workers: s.max_workers ?? 1,
  llm_max_workers: s.llm_max_workers ?? 5,
})

// UI sentinels — "Random" / "Default" map to null so the backend picks at random.
const fromForm = (f) => ({
  name: f.name,
  enabled: f.enabled,
  cadence: f.cadence,
  times: f.times,
  days: f.cadence === 'weekly' ? f.days : [],
  interval_hours: parseInt(f.interval_hours, 10) || 3,
  interval_start: f.interval_start,
  interval_end: f.interval_end,
  jitter_minutes: parseInt(f.jitter_minutes, 10) || 0,
  stagger_enabled: f.stagger_enabled,
  stagger_min_minutes: parseInt(f.stagger_min_minutes, 10) || 60,
  stagger_max_minutes: parseInt(f.stagger_max_minutes, 10) || 240,
  post_to_tiktok: f.post_to_tiktok,
  num_shorts: parseInt(f.num_shorts, 10) || 5,
  prompts: f.prompts,
  enable_emojis: f.enable_emojis,
  enable_emoji_animation: f.enable_emoji_animation,
  emoji_scale_factor: parseFloat(f.emoji_scale_factor),
  emoji_hold_duration: parseFloat(f.emoji_hold_duration),
  emoji_throw_max_count: parseInt(f.emoji_throw_max_count, 10) || 3,
  layout: f.layout === 'Random' ? null : f.layout,
  voice_id: f.voice_id === 'Random' ? null : f.voice_id,
  sub_animation_style: f.sub_animation_style === 'Random' ? null : f.sub_animation_style,
  words_per_screen: f.words_per_screen === 'Default' ? null : f.words_per_screen,
  single_word_mode: f.single_word_mode,
  bg_music_path: f.bg_music_path === 'Random' ? null : f.bg_music_path,
  script_temp: parseFloat(f.script_temp),
  meta_temp: parseFloat(f.meta_temp),
  max_workers: parseInt(f.max_workers, 10) || 1,
  llm_max_workers: parseInt(f.llm_max_workers, 10) || 5,
})

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const cadenceLabel = (s) => {
  if (s.cadence === 'interval') return `Every ${s.interval_hours}h`
  if (s.cadence === 'weekly') return 'Weekly'
  return 'Daily'
}

const summarizeSchedule = (s) => {
  const jitter = s.jitter_minutes > 0 ? ` ±${s.jitter_minutes} min` : ''
  const times = (s.times || []).join(', ')
  if (s.cadence === 'interval') {
    return `Every ${s.interval_hours}h from ${s.interval_start}–${s.interval_end}${jitter}`
  }
  if (s.cadence === 'weekly') {
    const days = (s.days || []).map((d) => DAY_NAMES[d - 1]).filter(Boolean)
    return `Weekly on ${days.join(', ')} at ${times}${jitter}`
  }
  return `Daily at ${times}${jitter}`
}

const formatNextRun = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Schedule() {
  const voices = useAppStore((s) => s.voices || [])

  const [schedules, setSchedules] = useState([])
  const [schedulerRunning, setSchedulerRunning] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [loadingError, setLoadingError] = useState(null)

  const [editorOpen, setEditorOpen] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState(null)
  const [form, setForm] = useState(createDefaultForm)
  const [saving, setSaving] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const [availablePrompts, setAvailablePrompts] = useState({})
  const [musicFiles, setMusicFiles] = useState([])
  const [runningNow, setRunningNow] = useState(null)

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const loadData = useCallback(async () => {
    try {
      const [schedData, statusData] = await Promise.all([
        api.fetchSchedules(),
        api.fetchScheduleStatus(),
      ])
      setSchedules(schedData?.schedules || [])
      setSchedulerRunning(!!statusData?.running)
      setLoadingError(null)
    } catch (err) {
      console.debug('Failed to fetch schedules', err)
      setLoadingError(err.message || 'Could not reach the server')
    } finally {
      setInitialLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 15000)
    return () => clearInterval(interval)
  }, [loadData])

  // Prompts + music for the editor modal (best-effort, mirrors BatchHeader).
  useEffect(() => {
    api.fetchPrompts()
      .then((data) => setAvailablePrompts(data || {}))
      .catch(() => { /* best-effort */ })
    api.fetchMusic()
      .then((data) => setMusicFiles(Array.isArray(data) ? data : []))
      .catch(() => { /* best-effort */ })
  }, [])

  // --- Card actions ----------------------------------------------------------

  const handleToggle = async (schedule) => {
    try {
      const res = await api.toggleSchedule(schedule.id)
      setSchedules((prev) => prev.map((s) => (s.id === schedule.id ? res.schedule : s)))
      toast.success(res.schedule.enabled ? 'Schedule enabled' : 'Schedule paused', {
        description: `'${res.schedule.name}' will ${res.schedule.enabled ? 'run on schedule' : 'not fire until re-enabled'}.`,
      })
    } catch (err) {
      toast.error('Failed to toggle schedule', { description: err.message })
    }
  }

  const handleRunNow = async (schedule) => {
    setRunningNow(schedule.id)
    try {
      const res = await api.runScheduleNow(schedule.id)
      if (res.status === 'running') {
        toast.success('Schedule fired', { description: res.message })
      } else if (res.status === 'skipped') {
        toast.info('Schedule skipped', { description: res.message })
      } else {
        toast.error('Run failed', { description: res.message || 'Unknown error' })
      }
      loadData()
    } catch (err) {
      toast.error('Failed to run schedule', { description: err.message })
    } finally {
      setRunningNow(null)
    }
  }

  const handleDelete = async (schedule) => {
    if (!window.confirm(`Delete schedule '${schedule.name}'?`)) return
    try {
      await api.deleteSchedule(schedule.id)
      setSchedules((prev) => prev.filter((s) => s.id !== schedule.id))
      toast.success('Schedule deleted', { description: `'${schedule.name}' removed.` })
    } catch (err) {
      toast.error('Failed to delete schedule', { description: err.message })
    }
  }

  // --- Editor ----------------------------------------------------------------

  const openCreate = () => {
    setEditingSchedule(null)
    setForm(createDefaultForm())
    setAdvancedOpen(false)
    setEditorOpen(true)
  }

  const openEdit = (schedule) => {
    setEditingSchedule(schedule)
    setForm(toForm(schedule))
    setAdvancedOpen(false)
    setEditorOpen(true)
  }

  const closeEditor = () => setEditorOpen(false)

  const updateTime = (index, value) => setForm((prev) => {
    const times = [...prev.times]
    times[index] = value
    return { ...prev, times }
  })

  const addTime = () => setForm((prev) => ({ ...prev, times: [...prev.times, '09:00'] }))

  const removeTime = (index) => setForm((prev) => ({
    ...prev,
    times: prev.times.filter((_, i) => i !== index),
  }))

  const toggleDay = (day) => setForm((prev) => ({
    ...prev,
    days: prev.days.includes(day)
      ? prev.days.filter((d) => d !== day)
      : [...prev.days, day].sort((a, b) => a - b),
  }))

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('Name required', { description: 'Give the schedule a name before saving.' })
      return
    }
    if (form.cadence !== 'interval') {
      const badTime = form.times.find((t) => !t || !/^\d{2}:\d{2}$/.test(t))
      if (badTime) {
        toast.error('Invalid time', { description: `'${badTime}' is not valid. Times must be in HH:MM format.` })
        return
      }
    }
    if (form.cadence === 'weekly' && form.days.length === 0) {
      toast.error('No days selected', { description: 'Pick at least one day of the week.' })
      return
    }
    if (form.stagger_enabled && form.stagger_min_minutes > form.stagger_max_minutes) {
      toast.error('Invalid stagger range', { description: 'Min gap must be less than or equal to Max gap.' })
      return
    }
    setSaving(true)
    try {
      const payload = fromForm(form)
      if (editingSchedule) {
        await api.updateSchedule(editingSchedule.id, payload)
        toast.success('Schedule updated', { description: `'${payload.name}' saved.` })
      } else {
        await api.createSchedule(payload)
        toast.success('Schedule created', { description: `'${payload.name}' is now scheduled.` })
      }
      setEditorOpen(false)
      loadData()
    } catch (err) {
      toast.error(editingSchedule ? 'Failed to update schedule' : 'Failed to create schedule', { description: err.message })
    } finally {
      setSaving(false)
    }
  }

  // Ensure a select always has an item matching the current value.
  const ensureOption = (current, options) => {
    const str = String(current)
    return options.includes(str) ? options : [str, ...options]
  }

  const musicValues = musicFiles.map((m) => `music/${m.filename}`)
  const currentMusicValue = form.bg_music_path && form.bg_music_path !== 'Random'
    ? form.bg_music_path
    : 'Random'

  const selectCls = 'bg-background border border-border rounded-md px-2 py-1 text-xs h-auto min-h-0 text-left'

  return (
    <div className="space-y-3 md:space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-6xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)] pb-28 md:pb-0">
      {/* Header */}
      <header className="shrink-0 flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-3">
        <div className="flex items-start gap-3">
          <div>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight flex items-center gap-2">
              <CalendarClock className="text-blue-500" size={22} />
              Scheduler
            </h1>
            <p className="text-xs md:text-sm text-muted-foreground mt-0.5">
              Automate batch generation and TikTok posting on a recurring schedule.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium",
            schedulerRunning
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : "bg-muted/40 text-muted-foreground border-border/50"
          )}>
            <span className={cn(
              "relative flex h-2 w-2",
              schedulerRunning && "animate-pulse"
            )}>
              <span className={cn(
                "absolute inline-flex h-full w-full rounded-full",
                schedulerRunning ? "bg-emerald-400 animate-ping opacity-75" : "bg-muted-foreground/50"
              )} />
              <span className={cn(
                "relative inline-flex rounded-full h-2 w-2",
                schedulerRunning ? "bg-emerald-500" : "bg-muted-foreground"
              )} />
            </span>
            {schedulerRunning ? 'Scheduler Active' : 'Scheduler Idle'}
          </span>

          <Button
            variant="default"
            onClick={openCreate}
            className="bg-blue-500 hover:bg-blue-600 text-white shadow-md shadow-blue-500/25 text-xs md:text-sm h-auto py-2 md:py-2 px-3"
          >
            <Plus size={14} />
            New Schedule
          </Button>
        </div>
      </header>

      {loadingError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-400 text-xs font-medium flex items-center gap-2 animate-in fade-in">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
          </span>
          {loadingError}
        </div>
      )}

      {/* Schedule list / empty state */}
      {initialLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="animate-pulse bg-secondary/40 rounded-xl h-40" />
          ))}
        </div>
      ) : schedules.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center text-muted-foreground space-y-3 py-24 bg-card border border-border rounded-xl shadow-sm">
          <div className="relative">
            <CalendarClock size={48} className="opacity-10" />
            <Sparkles size={18} className="absolute -top-1 -right-1 text-blue-400/30 animate-pulse" />
          </div>
          <div className="space-y-1 max-w-xs">
            <p className="text-sm font-medium text-foreground/60">No schedules yet</p>
            <p className="text-xs text-muted-foreground/60 leading-relaxed">
              Create a schedule to automate batch generation and posting.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={openCreate}
            className="text-xs gap-1.5 mt-2 bg-blue-500/5 border-blue-500/20 text-blue-400 hover:bg-blue-500/10"
          >
            <Plus size={12} />
            Create Schedule
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {schedules.map((schedule) => {
            const status = statusStyle(schedule.last_status)
            const nextRun = formatNextRun(schedule.next_run)
            return (
              <div
                key={schedule.id}
                className={cn(
                  "bg-card border border-border rounded-xl shadow-sm p-4 flex flex-col gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
                  schedule.enabled === false && "opacity-70"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-sm truncate">{schedule.name}</h3>
                    <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                        {cadenceLabel(schedule)}
                      </span>
                      {schedule.post_to_tiktok && (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-black text-white border border-white/15">
                          𝕋 TikTok
                        </span>
                      )}
                      <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full border flex items-center gap-1", status.cls)}>
                        <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
                        {status.label}
                      </span>
                    </div>
                  </div>
                  <Switch
                    checked={schedule.enabled !== false}
                    onCheckedChange={() => handleToggle(schedule)}
                    className="data-[state=checked]:bg-blue-500 shrink-0"
                  />
                </div>

                <p className="text-xs text-muted-foreground leading-relaxed">{summarizeSchedule(schedule)}</p>

                <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Clock size={12} className="text-blue-400 shrink-0" />
                  {nextRun ? (
                    <span>
                      Next: <span className="text-foreground font-medium">{nextRun}</span>
                    </span>
                  ) : (
                    <span className="italic">Not scheduled</span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 pt-1 border-t border-border/50 mt-auto">
                  <Button
                    variant="outline"
                    onClick={() => handleRunNow(schedule)}
                    disabled={runningNow === schedule.id}
                    className="h-auto py-1.5 px-2.5 text-xs gap-1.5 bg-secondary/40 hover:bg-secondary/70 border-border/50"
                  >
                    {runningNow === schedule.id ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Play size={12} />
                    )}
                    Run Now
                  </Button>
                  <div className="ml-auto flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEdit(schedule)}
                      title="Edit"
                      className="h-8 w-8 text-muted-foreground hover:text-blue-400 hover:bg-blue-500/10"
                    >
                      <Pencil size={14} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(schedule)}
                      title="Delete"
                      className="h-8 w-8 text-muted-foreground hover:text-red-400 hover:bg-red-500/10"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Editor Modal */}
      {/* ------------------------------------------------------------------ */}
      {editorOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm animate-in fade-in duration-150" onClick={closeEditor} />
          <div className="relative bg-card border border-border rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 slide-in-from-bottom-4 duration-200">
            {/* Title bar */}
            <div className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm border-b border-border px-5 py-3.5 flex items-center justify-between">
              <h2 className="text-base font-bold flex items-center gap-2">
                <CalendarClock size={18} className="text-blue-500" />
                {editingSchedule ? 'Edit Schedule' : 'New Schedule'}
              </h2>
              <button
                onClick={closeEditor}
                className="p-1.5 rounded-full hover:bg-secondary text-muted-foreground transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-6">
              {/* General */}
              <Section title="General">
                <div className="space-y-2">
                  <Label htmlFor="schedule-name" className="text-xs font-medium text-muted-foreground">Name</Label>
                  <Input
                    id="schedule-name"
                    type="text"
                    value={form.name}
                    onChange={(e) => setField('name', e.target.value)}
                    placeholder="e.g. Morning shorts"
                    className="bg-background"
                  />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Label className="text-xs font-medium text-muted-foreground">Enabled</Label>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">Fires runs while enabled</p>
                  </div>
                  <Switch
                    checked={form.enabled}
                    onCheckedChange={(v) => setField('enabled', v)}
                    className="data-[state=checked]:bg-blue-500"
                  />
                </div>
              </Section>

              {/* Schedule */}
              <Section title="Schedule">
                <div className="grid grid-cols-3 gap-1 bg-secondary/50 border border-border rounded-lg p-1">
                  {CADENCE_OPTIONS.map((c) => (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => setField('cadence', c.value)}
                      className={cn(
                        "px-3 py-2 rounded-md text-xs font-medium transition-all duration-200",
                        form.cadence === c.value
                          ? "bg-blue-500/15 text-blue-400 border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.15)]"
                          : "text-muted-foreground hover:text-foreground border border-transparent"
                      )}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>

                {(form.cadence === 'daily' || form.cadence === 'weekly') && (
                  <div className="space-y-2">
                    <Label className="text-xs font-medium text-muted-foreground">Times</Label>
                    {form.times.map((t, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <Input
                          type="time"
                          value={t}
                          onChange={(e) => updateTime(i, e.target.value)}
                          className="flex-1 bg-background"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          type="button"
                          onClick={() => removeTime(i)}
                          disabled={form.times.length <= 1}
                          className="h-9 w-9 text-muted-foreground hover:text-red-400 hover:bg-red-500/10 disabled:opacity-30"
                          title="Remove time"
                        >
                          <X size={15} />
                        </Button>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      type="button"
                      onClick={addTime}
                      className="text-xs h-auto py-1.5 px-2.5 gap-1.5 border-dashed bg-background/50"
                    >
                      <Plus size={12} />
                      Add Time
                    </Button>
                  </div>
                )}

                {form.cadence === 'weekly' && (
                  <div className="space-y-2">
                    <Label className="text-xs font-medium text-muted-foreground">Days of the week</Label>
                    <div className="flex gap-1.5">
                      {DAY_SHORT.map((label, idx) => {
                        const day = idx + 1
                        const active = form.days.includes(day)
                        return (
                          <button
                            key={day}
                            type="button"
                            onClick={() => toggleDay(day)}
                            title={DAY_NAMES[idx]}
                            className={cn(
                              "flex-1 h-9 rounded-md border text-xs font-medium transition-all duration-150",
                              active
                                ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                                : "bg-secondary/40 text-muted-foreground border-border/50 hover:text-foreground hover:bg-secondary/70"
                            )}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

                {form.cadence === 'interval' && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-medium text-muted-foreground">Every N hours</Label>
                      <Input
                        type="number"
                        min={1}
                        max={48}
                        value={form.interval_hours}
                        onChange={(e) => setField('interval_hours', e.target.value)}
                        className="bg-background"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-medium text-muted-foreground">Start</Label>
                      <Input
                        type="time"
                        value={form.interval_start}
                        onChange={(e) => setField('interval_start', e.target.value)}
                        className="bg-background"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-medium text-muted-foreground">End</Label>
                      <Input
                        type="time"
                        value={form.interval_end}
                        onChange={(e) => setField('interval_end', e.target.value)}
                        className="bg-background"
                      />
                    </div>
                  </div>
                )}
              </Section>

              {/* Randomness */}
              <Section title="Randomness">
                <div className="space-y-1.5">
                  <Label className="text-xs font-medium text-muted-foreground">Jitter ± minutes</Label>
                  <Input
                    type="number"
                    min={0}
                    max={120}
                    value={form.jitter_minutes}
                    onChange={(e) => setField('jitter_minutes', e.target.value)}
                    className="bg-background max-w-[140px]"
                  />
                  <p className="text-[10px] text-muted-foreground/50">
                    Randomize each scheduled run time within this window.
                  </p>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Label className="text-xs font-medium text-muted-foreground">Stagger posts</Label>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">Space TikTok posts across the day</p>
                  </div>
                  <Switch
                    checked={form.stagger_enabled}
                    onCheckedChange={(v) => setField('stagger_enabled', v)}
                    className="data-[state=checked]:bg-blue-500"
                  />
                </div>

                {form.stagger_enabled && (
                  <div className="grid grid-cols-2 gap-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-medium text-muted-foreground">Min gap (min)</Label>
                      <Input
                        type="number"
                        min={1}
                        value={form.stagger_min_minutes}
                        onChange={(e) => setField('stagger_min_minutes', e.target.value)}
                        className="bg-background"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-medium text-muted-foreground">Max gap (min)</Label>
                      <Input
                        type="number"
                        min={1}
                        value={form.stagger_max_minutes}
                        onChange={(e) => setField('stagger_max_minutes', e.target.value)}
                        className="bg-background"
                      />
                    </div>
                  </div>
                )}
              </Section>

              {/* Posting */}
              <Section title="Posting">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Label className="text-xs font-medium text-muted-foreground">Post to TikTok</Label>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">Auto-publish rendered shorts</p>
                  </div>
                  <Switch
                    checked={form.post_to_tiktok}
                    onCheckedChange={(v) => setField('post_to_tiktok', v)}
                    className="data-[state=checked]:bg-black"
                  />
                </div>
                {form.post_to_tiktok && (
                  <p className="text-[11px] text-muted-foreground/70 bg-secondary/30 border border-border/50 rounded-md px-3 py-2 animate-in fade-in">
                    TikTok session ID must be set in Settings.
                  </p>
                )}
              </Section>

              {/* Batch Config */}
              <Section title="Batch Config">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">Qty</Label>
                    <Select value={String(form.num_shorts)} onValueChange={(v) => setField('num_shorts', v)}>
                      <SelectTrigger className="bg-background"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {QUANTITY_OPTIONS.map((n) => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-medium text-muted-foreground">Prompts ({form.prompts.length})</Label>
                    <div className="flex items-center gap-2 text-[10px]">
                      <button
                        type="button"
                        onClick={() => setField('prompts', Object.keys(availablePrompts))}
                        className="text-blue-500 hover:underline"
                      >
                        Select All
                      </button>
                      <span className="text-muted-foreground">|</span>
                      <button
                        type="button"
                        onClick={() => setField('prompts', [])}
                        className="text-muted-foreground hover:underline"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="border border-border rounded-lg bg-background max-h-56 overflow-y-auto overscroll-contain">
                    {Object.keys(availablePrompts).length === 0 && (
                      <div className="p-3 text-xs text-muted-foreground text-center">No prompts found</div>
                    )}
                    {Object.keys(availablePrompts).map((key) => (
                      <Label key={key} className="flex items-start gap-3 p-2.5 hover:bg-secondary/50 rounded cursor-pointer transition-colors border-b border-border/30 last:border-b-0">
                        <div className="mt-0.5 flex-shrink-0 flex items-center justify-center w-4 h-4 rounded border border-border bg-secondary/40">
                          {form.prompts.includes(key) && <Check size={12} className="text-blue-500" />}
                        </div>
                        <input
                          type="checkbox"
                          className="hidden"
                          checked={form.prompts.includes(key)}
                          onChange={(e) => setField(
                            'prompts',
                            e.target.checked
                              ? [...form.prompts, key]
                              : form.prompts.filter((p) => p !== key)
                          )}
                        />
                        <div className="flex flex-col">
                          <span className="text-xs font-medium leading-none">{key}</span>
                          <span className="text-[10px] text-muted-foreground mt-1 line-clamp-2" title={availablePrompts[key]}>{availablePrompts[key]}</span>
                        </div>
                      </Label>
                    ))}
                  </div>
                </div>

                {/* Emoji controls */}
                <div className="border border-border rounded-lg overflow-hidden bg-background/50">
                  <div className="p-3 border-b border-border bg-secondary/30 flex items-center justify-between">
                    <Label className="text-xs font-medium text-muted-foreground cursor-pointer">😊 Emojis</Label>
                    <Switch
                      checked={form.enable_emojis}
                      onCheckedChange={(v) => setField('enable_emojis', v)}
                      className="data-[state=checked]:bg-yellow-500"
                    />
                  </div>
                  <div className="p-3 space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-medium text-muted-foreground">Animation</Label>
                      <Button
                        variant="outline"
                        type="button"
                        onClick={() => setField('enable_emoji_animation', !form.enable_emoji_animation)}
                        disabled={!form.enable_emojis}
                        className={cn(
                          "text-xs px-2.5 py-1 h-auto rounded-md font-medium border transition-all duration-200",
                          form.enable_emoji_animation
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                        )}
                      >
                        {form.enable_emoji_animation ? 'On' : 'Off'}
                      </Button>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-medium text-muted-foreground">Scale</Label>
                      <Select value={String(form.emoji_scale_factor)} onValueChange={(v) => setField('emoji_scale_factor', v)} disabled={!form.enable_emojis}>
                        <SelectTrigger className="w-20"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[0.5, 1.0, 1.5, 2.0, 2.5, 3.0].map((n) => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-medium text-muted-foreground">Hold Duration</Label>
                      <Select value={String(form.emoji_hold_duration)} onValueChange={(v) => setField('emoji_hold_duration', v)} disabled={!form.enable_emojis}>
                        <SelectTrigger className="w-20"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[0, 0.5, 1.0, 1.5, 2.0].map((n) => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-medium text-muted-foreground">Max / Word</Label>
                      <Select value={String(form.emoji_throw_max_count)} onValueChange={(v) => setField('emoji_throw_max_count', v)} disabled={!form.enable_emojis}>
                        <SelectTrigger className="w-20"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[1, 3, 5, 10, 15, 20].map((n) => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                {/* Advanced accordion */}
                <div className="border border-border rounded-lg overflow-hidden bg-background/50">
                  <button
                    type="button"
                    onClick={() => setAdvancedOpen(!advancedOpen)}
                    className="w-full flex items-center justify-between p-3 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <SlidersHorizontal size={14} className="text-violet-400" />
                      Advanced Batch Settings
                    </span>
                    {advancedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {advancedOpen && (
                    <div className="p-3 border-t border-border/50 space-y-3 animate-in fade-in slide-in-from-top-1 duration-200">
                      <Row label="Layout" hint="Split vs. full-screen backgrounds">
                        <Select value={String(form.layout)} onValueChange={(v) => setField('layout', v)}>
                          <SelectTrigger className={cn(selectCls, 'w-32')}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Random">Random</SelectItem>
                            <SelectItem value="Split-Screen">Split-Screen</SelectItem>
                            <SelectItem value="Full Screen">Full Screen</SelectItem>
                          </SelectContent>
                        </Select>
                      </Row>

                      <Row label="Voice" hint={form.voice_id !== 'Random' ? form.voice_id : 'Random voice per job'}>
                        <Select value={String(form.voice_id)} onValueChange={(v) => setField('voice_id', v)}>
                          <SelectTrigger className={cn(selectCls, 'w-44')}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Random">Random</SelectItem>
                            {voices.map((v) => (
                              <SelectItem key={v.value} value={v.value}>{v.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Row>

                      <Row label="Sub Animation" hint="Caption animation style">
                        <Select value={String(form.sub_animation_style)} onValueChange={(v) => setField('sub_animation_style', v)}>
                          <SelectTrigger className={cn(selectCls, 'w-40')}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Random">Random</SelectItem>
                            {ANIMATION_STYLES.map((a) => (
                              <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Row>

                      <Row label="Words / Screen" hint="Caption phrasing">
                        <Select value={String(form.words_per_screen)} onValueChange={(v) => setField('words_per_screen', v)}>
                          <SelectTrigger className={cn(selectCls, 'w-28')}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Default">Default</SelectItem>
                            <SelectItem value="1">1 word</SelectItem>
                            <SelectItem value="3">3 words</SelectItem>
                            <SelectItem value="sentence">Sentence</SelectItem>
                            <SelectItem value="random">Random</SelectItem>
                          </SelectContent>
                        </Select>
                      </Row>

                      <Row label="Single Word Mode" hint="One word on screen at a time">
                        <Switch
                          checked={!!form.single_word_mode}
                          onCheckedChange={(v) => setField('single_word_mode', v)}
                          className="data-[state=checked]:bg-violet-500"
                        />
                      </Row>

                      <Row label="Music" hint={form.bg_music_path !== 'Random' ? String(form.bg_music_path).replace(/^music\//, '') : 'Random track per job'}>
                        <Select value={String(currentMusicValue)} onValueChange={(v) => setField('bg_music_path', v)}>
                          <SelectTrigger className={cn(selectCls, 'w-44')}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Random">Random</SelectItem>
                            {musicFiles.map((m) => (
                              <SelectItem key={m.filename} value={`music/${m.filename}`} className="truncate">{m.filename}</SelectItem>
                            ))}
                            {!musicValues.includes(form.bg_music_path) && form.bg_music_path !== 'Random' && (
                              <SelectItem value={form.bg_music_path} className="truncate">{String(form.bg_music_path).replace(/^music\//, '')}</SelectItem>
                            )}
                            {musicFiles.length === 0 && (
                              <SelectItem value="__empty__" disabled>No music tracks found</SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                      </Row>

                      <div className="border-t border-border/40 pt-3 space-y-3">
                        <Row label="Script Temp" hint="LLM creativity (higher = more varied)">
                          <Select value={String(form.script_temp)} onValueChange={(v) => setField('script_temp', v)}>
                            <SelectTrigger className={cn(selectCls, 'w-20')}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {ensureOption(form.script_temp, TEMP_OPTIONS).map((t) => (
                                <SelectItem key={t} value={String(t)}>{String(t)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Row>
                        <Row label="Meta Temp" hint="Title & keyword generation">
                          <Select value={String(form.meta_temp)} onValueChange={(v) => setField('meta_temp', v)}>
                            <SelectTrigger className={cn(selectCls, 'w-20')}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {ensureOption(form.meta_temp, TEMP_OPTIONS).map((t) => (
                                <SelectItem key={t} value={String(t)}>{String(t)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Row>
                      </div>

                      <div className="border-t border-border/40 pt-3 space-y-3">
                        <Row label="Render Workers" hint="Parallel video renders per job">
                          <Select value={String(form.max_workers)} onValueChange={(v) => setField('max_workers', v)}>
                            <SelectTrigger className={cn(selectCls, 'w-20')}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {ensureOption(form.max_workers, WORKER_OPTIONS).map((w) => (
                                <SelectItem key={w} value={String(w)}>{w}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Row>
                        <Row label="LLM Workers" hint="Parallel script generation calls">
                          <Select value={String(form.llm_max_workers)} onValueChange={(v) => setField('llm_max_workers', v)}>
                            <SelectTrigger className={cn(selectCls, 'w-20')}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {ensureOption(form.llm_max_workers, LLM_WORKER_OPTIONS).map((w) => (
                                <SelectItem key={w} value={String(w)}>{w}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Row>
                      </div>
                    </div>
                  )}
                </div>
              </Section>
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 bg-card/95 backdrop-blur-sm border-t border-border px-5 py-3.5 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={closeEditor} className="text-xs h-auto py-2 px-3">
                Cancel
              </Button>
              <Button
                variant="default"
                onClick={handleSave}
                disabled={saving}
                className="bg-blue-500 hover:bg-blue-600 text-white shadow-md shadow-blue-500/25 text-xs h-auto py-2 px-3"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                {saving ? 'Saving...' : 'Save Schedule'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
