import { useState, useEffect, useCallback } from 'react'
import {
  Bug,
  Trash2,
  ArrowLeft,
  FileText,
  Brain,
  ChevronDown,
  RefreshCw,
  RotateCcw,
  Clock,
  ExternalLink,
  Terminal,
  MessageSquare,
  Scissors,
  Check,
  X,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(date, now) {
  const diff = now - date.getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 10) return 'just now'
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hrs = Math.floor(min / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function formatAbsolute(date) {
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function parseDate(value) {
  if (!value) return null
  const d = new Date(value)
  return isNaN(d.getTime()) ? null : d
}

// Split raw response text into [text, isThinkBlock] segments so <think>
// blocks can be highlighted while preserving the surrounding whitespace.
function splitThinkBlocks(text) {
  if (!text) return [{ text: '', think: false }]
  const segments = []
  const regex = /<think[\s\S]*?<\/think>/gi
  let lastIndex = 0
  for (const match of text.matchAll(regex)) {
    if (match.index > lastIndex) {
      segments.push({ text: text.slice(lastIndex, match.index), think: false })
    }
    segments.push({ text: match[0], think: true })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), think: false })
  }
  return segments.length > 0 ? segments : [{ text, think: false }]
}

// ---------------------------------------------------------------------------
// Small shared UI pieces
// ---------------------------------------------------------------------------

function Pill({ className, children }) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium',
      className
    )}>
      {children}
    </span>
  )
}

const STAT_ACCENTS = {
  amber: 'text-amber-400 bg-amber-500/10 border-amber-500/25',
  violet: 'text-violet-400 bg-violet-500/10 border-violet-500/25',
  emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25',
  red: 'text-red-400 bg-red-500/10 border-red-500/25',
}

function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="bg-card border border-border/60 rounded-xl p-4 flex items-center gap-3 shadow-sm">
      <div className={cn('w-10 h-10 rounded-lg border flex items-center justify-center shrink-0', STAT_ACCENTS[accent])}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground font-medium truncate">{label}</p>
        <p className="text-xl font-bold leading-tight tabular-nums">{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{sub}</p>}
      </div>
    </div>
  )
}

function CollapsibleSection({ title, icon, label, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-card border border-border/60 rounded-xl overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-secondary/10 transition-colors group"
      >
        <div className="flex items-center gap-2 min-w-0">
          {icon}
          <span className="text-sm font-semibold">{title}</span>
          {label && (
            <span className="hidden sm:inline text-[11px] text-muted-foreground truncate">{label}</span>
          )}
        </div>
        <ChevronDown
          size={16}
          className={cn('text-muted-foreground shrink-0 transition-transform duration-200', open && 'rotate-180')}
        />
      </button>
      <div className={cn(
        'grid transition-all duration-300 ease-in-out',
        open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
      )}>
        <div className="overflow-hidden">
          <div className="px-4 pb-4">{children}</div>
        </div>
      </div>
    </div>
  )
}

function CodeBlock({ children, empty = '—', className }) {
  return (
    <pre className={cn(
      'text-xs font-mono leading-relaxed whitespace-pre-wrap text-foreground/85 bg-background border border-border/50 rounded-lg p-3 max-h-72 overflow-y-auto',
      className
    )}>
      {children || empty}
    </pre>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const TABLE_HEADERS = ['#', 'Title', 'Model', 'Generated At', 'Think', 'Stripped', 'Output']
const SKELETON_WIDTHS = [40, 180, 130, 120, 48, 96, 180]

export default function LLMDebug() {
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [now, setNow] = useState(Date.now())

  const [selected, setSelected] = useState(null) // summary record for the open row
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)

  // Keep relative timestamps fresh
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchRecords = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const data = await api.fetchLLMDebugRecords()
      setRecords(data.records || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  // Load the full record on demand when a row is clicked — keeps the list payload small.
  const openRecord = async (record) => {
    setSelected(record)
    setDetail(null)
    setDetailLoading(true)
    setDetailError(null)
    try {
      const data = await api.fetchLLMDebugRecord(record.base_name)
      setDetail({ ...data, base_name: record.base_name })
    } catch (err) {
      setDetailError(err.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const goBack = () => {
    setSelected(null)
    setDetail(null)
    setDetailError(null)
  }

  const handleDelete = async (record) => {
    const confirmed = window.confirm(
      `Delete this debug record?\n\n"${record.title || record.base_name}"\n\nThe raw response, prompts, and diagnostics will be permanently removed.`
    )
    if (!confirmed) return
    try {
      await api.deleteLLMDebugRecord(record.base_name)
      toast.success('Record deleted', { description: `${record.base_name} was removed.` })
      setRecords((prev) => prev.filter((r) => r.base_name !== record.base_name))
      if (selected?.base_name === record.base_name) goBack()
    } catch (err) {
      toast.error('Delete failed', { description: err.message })
    }
  }

  const renderTime = (value) => {
    const d = parseDate(value)
    if (!d) return <span className="text-xs text-muted-foreground">—</span>
    return (
      <span className="flex flex-col leading-tight">
        <span className="text-xs text-foreground/80 font-medium">{timeAgo(d, now)}</span>
        <span className="text-[10px] text-muted-foreground/70">{formatAbsolute(d)}</span>
      </span>
    )
  }

  // ------------------------------ Detail view ------------------------------

  if (selected) {
    const diag = detail?.diagnostics || {}
    const thinkCount = diag.raw_think_count ?? 0
    const removedAnything = !!diag.stripped_removed_anything
    const charsRemoved = diag.stripped_chars_removed ?? 0
    const stripSub = removedAnything
      ? 'think content was removed'
      : thinkCount > 0
        ? 'blocks present — NOT removed!'
        : 'no think content present'
    const generatedAt = parseDate(detail?.generated_at)
    const rawSegments = splitThinkBlocks(detail?.raw_response)

    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <Button
            variant="ghost"
            size="sm"
            onClick={goBack}
            className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
          >
            <ArrowLeft size={16} />
            Back to records
          </Button>
          <div className="mt-3 h-px bg-gradient-to-r from-primary/30 via-primary/10 to-transparent" />
        </header>

        {detailLoading ? (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="bg-card border border-border/60 rounded-xl p-5 animate-pulse">
              <div className="h-5 w-40 bg-secondary/30 rounded" />
              <div className="mt-3 h-7 w-64 bg-secondary/30 rounded" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-20 bg-card border border-border/60 rounded-xl animate-pulse" />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="h-80 bg-card border border-border/60 rounded-xl animate-pulse" />
              <div className="h-80 bg-card border border-border/60 rounded-xl animate-pulse" />
            </div>
          </div>
        ) : detailError ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards">
            <div className="bg-card border border-border/60 rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
              <div className="p-4 rounded-full bg-destructive/10 border border-destructive/20">
                <AlertTriangle size={36} className="text-destructive/60" />
              </div>
              <div>
                <p className="text-lg font-semibold text-foreground mb-1">Failed to load record</p>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  The full debug record could not be fetched. It may have been deleted or the sidecar file may be missing.
                </p>
              </div>
              <p className="text-xs text-destructive/70 bg-destructive/5 rounded-md px-3 py-1.5 font-mono max-w-lg truncate">
                {detailError}
              </p>
              <Button variant="outline" onClick={goBack} className="gap-1.5">
                <ArrowLeft size={14} />
                Back to list
              </Button>
            </div>
          </div>
        ) : detail ? (
          <>
            {/* Header card */}
            <div className="bg-card border border-border/60 rounded-xl p-5 shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Pill className="bg-blue-500/15 text-blue-400 border-blue-500/30">
                      Job #{detail.job_index}
                    </Pill>
                    {detail.model && (
                      <Pill className="bg-violet-500/15 text-violet-300 border-violet-500/30">
                        <Brain size={11} />
                        {detail.model}
                      </Pill>
                    )}
                    {detail.script_temp != null && (
                      <Pill className="bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
                        temp {detail.script_temp}
                      </Pill>
                    )}
                  </div>
                  <h2 className="text-xl md:text-2xl font-bold mt-2">{detail.title || 'Untitled script'}</h2>
                  {detail.hashtags && (
                    <p className="text-xs text-cyan-300/80 mt-1 font-medium">{detail.hashtags}</p>
                  )}
                  <p className="text-[11px] font-mono text-muted-foreground mt-2 truncate">{detail.base_name}</p>
                </div>
                <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
                  <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <Clock size={12} />
                    {generatedAt ? `${timeAgo(generatedAt, now)} · ${formatAbsolute(generatedAt)}` : '—'}
                  </span>
                  {detail.output_filename && (
                    <a
                      href={`/output/${encodeURIComponent(detail.output_filename)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/25 rounded-lg px-3 py-1.5 transition-colors"
                    >
                      <ExternalLink size={12} />
                      View Video
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Diagnostic summary */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:100ms]">
              <StatCard
                accent="amber"
                icon={<Brain size={18} />}
                label="Think Blocks"
                value={thinkCount}
                sub="raw <think> occurrences"
              />
              <StatCard
                accent="violet"
                icon={<Scissors size={18} />}
                label="Chars Removed"
                value={charsRemoved}
                sub="by strip_think_blocks"
              />
              <StatCard
                accent={removedAnything ? 'emerald' : thinkCount > 0 ? 'red' : 'violet'}
                icon={removedAnything ? <Check size={18} /> : <X size={18} />}
                label="Stripped Anything"
                value={removedAnything ? 'Yes' : 'No'}
                sub={stripSub}
              />
            </div>

            {/* Raw Response + Final Script side-by-side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:150ms]">
              <div className="bg-card border border-border/60 rounded-xl shadow-sm overflow-hidden flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/20 shrink-0">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Terminal size={16} className="text-amber-400" />
                    Raw Response
                  </h3>
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400 px-2 py-0.5 text-[11px] font-medium">
                    <Brain size={11} />
                    {thinkCount} block{thinkCount === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="max-h-[480px] overflow-y-auto p-4">
                  {rawSegments.length > 0 ? (
                    <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap text-foreground/85">
                      {rawSegments.map((seg, i) => seg.think ? (
                        <mark key={i} className="bg-amber-500/20 text-amber-100 rounded-sm px-0.5">
                          {seg.text}
                        </mark>
                      ) : (
                        <span key={i}>{seg.text}</span>
                      ))}
                    </pre>
                  ) : (
                    <p className="text-xs text-muted-foreground">No raw response captured.</p>
                  )}
                </div>
              </div>

              <div className="bg-card border border-border/60 rounded-xl shadow-sm overflow-hidden flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-secondary/20 shrink-0">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <FileText size={16} className="text-emerald-400" />
                    Final Script
                  </h3>
                  <span className="text-[11px] text-muted-foreground">what the video speaks</span>
                </div>
                <div className="max-h-[480px] overflow-y-auto p-4">
                  {detail.final_script ? (
                    <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap text-foreground/85">
                      {detail.final_script}
                    </pre>
                  ) : (
                    <p className="text-xs text-muted-foreground">No final script recorded.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Collapsible sections */}
            <div className="space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:200ms]">
              <CollapsibleSection
                title="Stripped Script"
                icon={<Scissors size={16} className="text-violet-400" />}
                label="after strip_think_blocks, before title/hashtag extraction"
              >
                <CodeBlock>{detail.stripped_script}</CodeBlock>
              </CollapsibleSection>

              {detail.thinking_content && (
                <CollapsibleSection
                  defaultOpen
                  title="Thinking Content"
                  icon={<Brain size={16} className="text-amber-400" />}
                  label="streamed reasoning_content"
                >
                  <CodeBlock className="border-amber-500/20">{detail.thinking_content}</CodeBlock>
                </CollapsibleSection>
              )}

              <CollapsibleSection
                title="System Prompt"
                icon={<Terminal size={16} className="text-cyan-400" />}
                label="prompt sent to the LLM"
              >
                <CodeBlock>{detail.system_prompt}</CodeBlock>
              </CollapsibleSection>

              <CollapsibleSection
                title="User Prompt"
                icon={<MessageSquare size={16} className="text-indigo-400" />}
                label="generation request"
              >
                <CodeBlock>{detail.prompt}</CodeBlock>
              </CollapsibleSection>
            </div>
          </>
        ) : null}
      </div>
    )
  }

  // ------------------------------- List view -------------------------------

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <header className="animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2">
              <Bug className="text-amber-400" />
              LLM Debug
            </h1>
            <p className="text-xs md:text-sm text-muted-foreground mt-1">
              Inspect raw LLM generations to investigate why thinking blocks are sometimes not stripped from video scripts.
            </p>
          </div>
          <div className="flex items-center gap-2 self-end sm:self-auto">
            {records && records.length > 0 && (
              <span className="text-[11px] text-muted-foreground/60">
                {records.length} record{records.length === 1 ? '' : 's'}
              </span>
            )}
            <Button
              onClick={() => fetchRecords(true)}
              disabled={refreshing}
              variant="ghost"
              size="icon"
              className="text-muted-foreground/40 hover:text-primary"
              title="Refresh records"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            </Button>
          </div>
        </div>
        <div className="mt-4 h-px bg-gradient-to-r from-amber-500/30 via-primary/10 to-transparent" />
      </header>

      {loading ? (
        <div className="bg-card border border-border/60 rounded-xl overflow-hidden shadow-sm animate-in fade-in duration-300">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-border bg-secondary/20">
                  {TABLE_HEADERS.map((h) => (
                    <th key={h} className="px-4 py-3 font-medium">{h}</th>
                  ))}
                  <th className="px-4 py-3 w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {[0, 1, 2, 3, 4].map((i) => (
                  <tr key={i}>
                    {SKELETON_WIDTHS.map((w, j) => (
                      <td key={j} className="px-4 py-4">
                        <div className="h-3.5 bg-secondary/30 rounded animate-pulse" style={{ width: w }} />
                      </td>
                    ))}
                    <td className="px-4 py-4">
                      <div className="h-6 w-6 bg-secondary/30 rounded animate-pulse" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : error ? (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards">
          <div className="bg-card border border-border/60 rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
            <div className="p-4 rounded-full bg-destructive/10 border border-destructive/20">
              <AlertTriangle size={36} className="text-destructive/60" />
            </div>
            <div>
              <p className="text-lg font-semibold text-foreground mb-1">Failed to load debug records</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                The server returned an error while listing LLM debug records.
              </p>
            </div>
            <p className="text-xs text-destructive/70 bg-destructive/5 rounded-md px-3 py-1.5 font-mono max-w-lg truncate">
              {error}
            </p>
            <Button onClick={() => fetchRecords()} variant="outline" className="gap-1.5">
              <RotateCcw size={14} />
              Retry
            </Button>
          </div>
        </div>
      ) : records.length === 0 ? (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:150ms]">
          <div className="bg-card border border-border/60 rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
            <div className="p-4 rounded-full bg-secondary/20 border border-border/30">
              <Bug size={36} className="text-muted-foreground/40" />
            </div>
            <div>
              <p className="text-lg font-semibold text-foreground mb-1">No debug records yet</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                LLM debug records will appear here after batch generations. Each record captures the raw model
                response, the stripped script, and diagnostics about think-block removal.
              </p>
            </div>
            <a
              href="/batch"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors bg-primary/10 hover:bg-primary/15 rounded-lg px-4 py-2 border border-primary/20"
            >
              Go to Batch
            </a>
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border/60 rounded-xl overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-backwards [animation-delay:150ms]">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-border bg-secondary/20">
                  {TABLE_HEADERS.map((h) => (
                    <th key={h} className="px-4 py-3 font-medium">{h}</th>
                  ))}
                  <th className="px-4 py-3 w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {records.map((record) => {
                  const thinkCount = record.diagnostics?.raw_think_count ?? 0
                  const removedAnything = !!record.diagnostics?.stripped_removed_anything
                  const charsRemoved = record.diagnostics?.stripped_chars_removed ?? 0
                  return (
                    <tr
                      key={record.base_name}
                      onClick={() => openRecord(record)}
                      className="cursor-pointer hover:bg-secondary/10 transition-colors group"
                    >
                      <td className="px-4 py-3">
                        <span className="text-sm font-semibold text-blue-400 tabular-nums">
                          #{record.job_index ?? '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate max-w-[220px]">
                          {record.title || 'Untitled'}
                        </p>
                        <p className="text-[10px] font-mono text-muted-foreground/70 truncate max-w-[220px]">
                          {record.base_name}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono text-violet-300/90">{record.model || '—'}</span>
                      </td>
                      <td className="px-4 py-3">{renderTime(record.generated_at)}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'inline-flex items-center justify-center min-w-[32px] rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums',
                          thinkCount > 0
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                            : 'bg-secondary/40 text-muted-foreground border-border'
                        )}>
                          {thinkCount}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {thinkCount === 0 ? (
                          <span className="text-xs text-muted-foreground/70">—</span>
                        ) : removedAnything ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400">
                            <Check size={13} />
                            {charsRemoved} chars
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-red-400">
                            <X size={13} />
                            not stripped
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {record.output_filename ? (
                          <a
                            href={`/output/${encodeURIComponent(record.output_filename)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-blue-400 transition-colors max-w-[180px] truncate"
                            title={record.output_filename}
                          >
                            {record.output_filename}
                            <ExternalLink size={11} className="shrink-0" />
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground/60">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => { e.stopPropagation(); handleDelete(record) }}
                          className="text-muted-foreground/40 hover:text-red-400 hover:bg-red-500/10 h-8 w-8"
                          title="Delete record"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
