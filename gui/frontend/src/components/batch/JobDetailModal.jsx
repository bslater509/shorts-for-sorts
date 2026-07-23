import { Activity, CheckCircle2, XCircle, Clock, Loader2, X, Sparkles, Type, Smile, Volume2, Film, FileText, MessageSquare, Terminal } from 'lucide-react'
import MultiSegmentProgressBar from './MultiSegmentProgressBar'

const JobDetailModal = ({ job, onClose, progress }) => {
  if (!job) return null

  const isDone = job.status === 'Done'
  const isFailed = job.failed || job.status?.startsWith('Failed')
  const isQueued = job.status === 'Queued'
  const isRunning = !isDone && !isFailed && !isQueued

  const p = job.progress || 0

  const statusBadge = (status, icon, color) => (
    <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold border ${color}`}>
      {icon} {status}
    </span>
  )

  const SettingRow = ({ label, value }) => (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-b-0">
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
      <span className="text-xs text-foreground font-mono">{value ?? '—'}</span>
    </div>
  )

  const Section = ({ title, icon, children }) => (
    <div className="bg-secondary/20 border border-border/40 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-3">{icon} {title}</h3>
      <div className="divide-y divide-border/20">
        {children}
      </div>
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border bg-secondary/20 shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold">Job #{job.id}</h2>
            {isDone && statusBadge('Done', <CheckCircle2 size={14} />, 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10')}
            {isFailed && statusBadge('Failed', <XCircle size={14} />, 'text-red-400 border-red-500/30 bg-red-500/10')}
            {isQueued && statusBadge('Queued', <Clock size={14} />, 'text-muted-foreground border-border bg-muted/30')}
            {isRunning && statusBadge('Running', <Loader2 size={14} className="animate-spin" />, 'text-blue-400 border-blue-500/30 bg-blue-500/10')}
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-secondary/50 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Topic */}
          <div>
            <p className="text-sm text-muted-foreground font-medium mb-1">Topic</p>
            <p className="text-sm font-semibold">{job.topic || 'Waiting for topic...'}</p>
            <p className="text-xs text-muted-foreground mt-1">{job.voice_name || '—'} · {job.layout || '—'}</p>
          </div>

          {/* Progress Section */}
          <Section title="Progress" icon={<Activity size={16} className="text-blue-400" />}>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs font-medium text-blue-400">{job.status}</span>
                <span className="text-xs font-bold">{p}%</span>
              </div>
              <MultiSegmentProgressBar progress={p} segments={progress} />
              <div className="flex gap-4">
                <SettingRow label="Elapsed" value={job.elapsed} />
                <SettingRow label="ETA" value={job.eta} />
              </div>
            </div>
          </Section>

          {/* AI Settings */}
          <Section title="AI Settings" icon={<Sparkles size={16} className="text-purple-400" />}>
            <SettingRow label="Model" value={job.model || '—'} />
            <SettingRow label="Script Temp" value={job.script_temp || '—'} />
            <SettingRow label="Meta Temp" value={job.meta_temp || '—'} />
            <SettingRow label="Max Words" value={job.settings?.max_words || '—'} />
          </Section>

          {/* Text / Subtitles */}
          <Section title="Text &amp; Subtitles" icon={<Type size={16} className="text-amber-400" />}>
            <SettingRow label="Font" value={job.sub_font || '—'} />
            <SettingRow label="Font Size" value={job.sub_size ? `${job.sub_size}px` : '—'} />
            <SettingRow label="Color" value={job.sub_color || '—'} />
            <SettingRow label="Highlight" value={job.sub_highlight || '—'} />
            <SettingRow label="Outline" value={job.sub_outline || '—'} />
            <SettingRow label="Outline Width" value={job.sub_outline_width || '—'} />
            <SettingRow label="Bold" value={job.sub_bold ? 'Yes' : 'No'} />
            <SettingRow label="Uppercase" value={job.sub_uppercase ? 'Yes' : 'No'} />
            <SettingRow label="Animation" value={job.sub_animation_style || '—'} />
            <SettingRow label="Words / Screen" value={job.words_per_screen || '—'} />
            <SettingRow label="Word Pop" value={job.word_pop ? `Yes (${job.word_pop_scale}x)` : 'No'} />
            <SettingRow label="Inactive Dim" value={job.inactive_dim ? `Yes (${job.inactive_alpha})` : 'No'} />
            <SettingRow label="Single Word" value={job.single_word_mode ? 'Yes' : 'No'} />
            <SettingRow label="Border Style" value={job.sub_border_style || '—'} />
            <SettingRow label="Shadow Width" value={job.sub_shadow_width || '—'} />
            <SettingRow label="BG Color" value={job.sub_bg_color || '—'} />
            <SettingRow label="BG Alpha" value={job.sub_bg_alpha || '—'} />
          </Section>

          {/* Emoji Settings */}
          <Section title="Emoji" icon={<Smile size={16} className="text-yellow-400" />}>
            <SettingRow label="Enabled" value={job.enable_emojis ? 'Yes' : 'No'} />
            <SettingRow label="Animation" value={job.enable_emoji_animation ? 'On' : 'Off'} />
            <SettingRow label="Scale" value={job.emoji_scale_factor || '—'} />
            <SettingRow label="Hold Duration" value={job.emoji_hold_duration ? `${job.emoji_hold_duration}s` : '—'} />
            <SettingRow label="Max / Word" value={job.emoji_throw_max_count || '—'} />
            <SettingRow label="Position" value={job.emoji_position || '—'} />
            <SettingRow label="Style" value={job.emoji_style || '—'} />
          </Section>

          {/* Audio Settings */}
          <Section title="Audio" icon={<Volume2 size={16} className="text-green-400" />}>
            <SettingRow label="Voice" value={job.voice_name || job.voice_id || '—'} />
            <SettingRow label="Voice Speed" value={job.voice_speed || '—'} />
            <SettingRow label="Music Volume" value={job.music_volume || '—'} />
            <SettingRow label="Voice Volume" value={job.voice_volume || '—'} />
          </Section>

          {/* Video Settings */}
          <Section title="Video" icon={<Film size={16} className="text-rose-400" />}>
            <SettingRow label="Layout" value={job.layout || '—'} />
            <SettingRow label="Output" value={job.output_filename || '—'} />
          </Section>

          {/* Generated Content (only if available) */}
          {(job.generated_title || job.generated_hashtags || job.script_text) && (
            <Section title="Generated Content" icon={<FileText size={16} className="text-emerald-400" />}>
              {job.generated_title && <SettingRow label="Title" value={job.generated_title} />}
              {job.generated_hashtags && <SettingRow label="Hashtags" value={job.generated_hashtags} />}
              {job.script_text && (
                <div className="py-2">
                  <span className="text-xs text-muted-foreground font-medium">Script</span>
                  <pre className="text-xs text-foreground mt-1 whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-48 overflow-y-auto font-mono leading-relaxed">{job.script_text}</pre>
                </div>
              )}
            </Section>
          )}

          {/* Prompt (system prompt) */}
          {job.system_prompt && (
            <Section title="System Prompt" icon={<MessageSquare size={16} className="text-indigo-400" />}>
              <pre className="text-xs text-foreground whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-40 overflow-y-auto font-mono leading-relaxed">{job.system_prompt}</pre>
            </Section>
          )}

          {/* Raw Prompt */}
          {job.prompt && (
            <Section title="Generation Prompt" icon={<Terminal size={16} className="text-cyan-400" />}>
              <pre className="text-xs text-foreground whitespace-pre-wrap bg-background border border-border/50 rounded-lg p-3 max-h-32 overflow-y-auto font-mono leading-relaxed">{job.prompt}</pre>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}

export default JobDetailModal
