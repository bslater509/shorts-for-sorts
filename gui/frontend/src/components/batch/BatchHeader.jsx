import { Layers, ChevronDown, Check, Play, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'

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
  return (
    <header className="shrink-0 flex flex-col sm:flex-row items-start sm:justify-between gap-3">
      <div>
        <h1 className="text-xl md:text-2xl font-bold tracking-tight flex items-center gap-2">
          <Layers className="text-blue-500" size={22} />
          Batch Generator
        </h1>
        <p className="text-xs md:text-sm text-muted-foreground mt-0.5">Generate multiple videos autonomously.</p>
      </div>

      <div className="flex items-center gap-2 bg-secondary/50 border border-border rounded-xl p-1.5 shrink-0 shadow-sm flex-wrap">
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
          <div className="flex items-center gap-1.5 bg-secondary/30 border border-border rounded-lg p-1.5 animate-in fade-in slide-in-from-top-2 duration-200 flex-wrap">
            <div className="flex items-center gap-1">
              <Label className="text-[9px] font-medium text-muted-foreground whitespace-nowrap">Anim</Label>
              <Button
                variant="outline"
                onClick={() => setEnableEmojiAnimation(!enableEmojiAnimation)}
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium border h-auto ${
                  enableEmojiAnimation
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                    : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                }`}
              >
                {enableEmojiAnimation ? 'On' : 'Off'}
              </Button>
            </div>
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-1">
              <Label className="text-[9px] font-medium text-muted-foreground whitespace-nowrap">Scale</Label>
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
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-1">
              <Label className="text-[9px] font-medium text-muted-foreground whitespace-nowrap">Hold</Label>
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
            <div className="w-px h-4 bg-border" />
            <div className="flex items-center gap-1">
              <Label className="text-[9px] font-medium text-muted-foreground whitespace-nowrap">Max/Word</Label>
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

        <Button
          variant="default"
          onClick={handleStart}
          disabled={inProgress || isStarting || selectedPrompts.length === 0}
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium text-xs bg-blue-500 hover:bg-blue-600 text-white shadow-md disabled:opacity-50 h-auto"
        >
          {isStarting ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          Start Batch
        </Button>
      </div>
    </header>
  )
}

export default BatchHeader
