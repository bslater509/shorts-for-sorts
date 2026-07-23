import { Layers, ChevronDown, Check, Play, Loader2 } from 'lucide-react'

const AVAILABLE_EMOJI_STYLES = [
  { id: 'apple', label: 'Apple' },
  { id: 'twemoji', label: 'Twemoji' },
  { id: 'google', label: 'Google' },
  { id: 'facebook', label: 'Facebook' },
  { id: 'openmoji', label: 'OpenMoji' }
]

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
  emojiStyles,
  setEmojiStyles,
  handleStart,
  isStarting
}) => {
  return (
    <header className="shrink-0 flex flex-col sm:flex-row items-start sm:justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Layers className="text-blue-500" />
          Batch Generator
        </h1>
        <p className="text-muted-foreground mt-1">Generate multiple videos autonomously using AI selected topics and configured layouts.</p>
      </div>

      <div className="flex items-center gap-3 bg-secondary/50 border border-border rounded-xl p-2 shrink-0 shadow-sm flex-wrap">
        <div className="flex items-center gap-2 px-2">
          <label className="text-sm font-medium">Quantity</label>
          <select
            className="w-16 bg-background border border-border rounded-md px-2 py-1 text-sm text-center appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            value={numShorts}
            onChange={(e) => {
              updateAppState({ batch_num_shorts: parseInt(e.target.value) })
              saveCurrentState()
            }}
            disabled={inProgress}
          >
            {[1,2,3,4,5,10,15,20,25,30,40,50].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div className="relative">
          <button
            onClick={() => setShowPromptDropdown(!showPromptDropdown)}
            disabled={inProgress}
            className="flex items-center gap-2 bg-background border border-border rounded-md px-3 py-1.5 text-sm font-medium hover:bg-secondary/50 transition-colors disabled:opacity-50"
          >
            Prompts ({selectedPrompts.length}) <ChevronDown size={14} />
          </button>
          {showPromptDropdown && !inProgress && (
            <div className="absolute top-full mt-2 right-0 md:right-auto md:left-0 w-72 bg-card border border-border rounded-lg shadow-xl z-50 overflow-hidden flex flex-col max-h-80">
              <div className="p-2 border-b border-border bg-secondary/30 flex justify-between items-center text-xs">
                <span className="font-semibold text-muted-foreground">Select Prompts</span>
                <div className="space-x-2">
                  <button onClick={() => setSelectedPrompts(Object.keys(availablePrompts))} className="text-blue-500 hover:underline">All</button>
                  <button onClick={() => setSelectedPrompts([])} className="text-muted-foreground hover:underline">None</button>
                </div>
              </div>
              <div className="overflow-y-auto p-1">
                {Object.keys(availablePrompts).length === 0 && <div className="p-2 text-xs text-muted-foreground text-center">No prompts found</div>}
                {Object.keys(availablePrompts).map(key => (
                  <label key={key} className="flex items-start gap-2 p-2 hover:bg-secondary/50 rounded cursor-pointer">
                    <div className="mt-0.5 flex-shrink-0 flex items-center justify-center w-4 h-4 rounded border border-border bg-background">
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
                      <span className="text-sm font-medium leading-none">{key}</span>
                      <span className="text-xs text-muted-foreground mt-1 line-clamp-3" title={availablePrompts[key]}>{availablePrompts[key]}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => setEnableEmojis(!enableEmojis)}
          disabled={inProgress}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all border ${
            enableEmojis
              ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
              : 'bg-muted/50 text-muted-foreground/60 border-border/30'
          } disabled:opacity-50`}
        >
          {enableEmojis ? '😊 Emoji' : '🚫 No Emoji'}
        </button>

        {enableEmojis && (
          <div className="flex items-center gap-2 bg-secondary/30 border border-border rounded-lg p-2 animate-in fade-in slide-in-from-top-2 duration-200 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Anim</label>
              <button
                onClick={() => setEnableEmojiAnimation(!enableEmojiAnimation)}
                className={`text-xs px-2 py-1 rounded font-medium transition-all border ${
                  enableEmojiAnimation
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                    : 'bg-muted/50 text-muted-foreground/60 border-border/30'
                }`}
              >
                {enableEmojiAnimation ? 'On' : 'Off'}
              </button>
            </div>
            <div className="w-px h-5 bg-border" />
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Scale</label>
              <select
                className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                value={emojiScaleFactor}
                onChange={(e) => {
                  updateAppState({ emoji_scale_factor: parseFloat(e.target.value) })
                  saveCurrentState()
                }}
              >
                {[0.5,1.0,1.5,2.0,2.5,3.0].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div className="w-px h-5 bg-border" />
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Hold</label>
              <select
                className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                value={emojiHoldDuration}
                onChange={(e) => {
                  updateAppState({ emoji_hold_duration: parseFloat(e.target.value) })
                  saveCurrentState()
                }}
              >
                {[0,0.5,1.0,1.5,2.0].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div className="w-px h-5 bg-border" />
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Max/Word</label>
              <select
                className="w-16 bg-background border border-border rounded-md px-1 py-1 text-xs text-center appearance-none cursor-pointer"
                value={emojiThrowMaxCount}
                onChange={(e) => {
                  updateAppState({ emoji_throw_max_count: parseInt(e.target.value) })
                  saveCurrentState()
                }}
              >
                {[1,3,5,10,15,20].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div className="w-px h-5 bg-border" />
            <div className="flex items-center gap-1.5">
              <label className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">Styles</label>
              <div className="flex bg-background border border-border rounded-md overflow-hidden">
                {AVAILABLE_EMOJI_STYLES.map(style => {
                  const active = emojiStyles.includes(style.id)
                  return (
                    <button
                      key={style.id}
                      onClick={() => {
                        if (active && emojiStyles.length > 1) {
                          setEmojiStyles(emojiStyles.filter(s => s !== style.id))
                        } else if (!active) {
                          setEmojiStyles([...emojiStyles, style.id])
                        }
                      }}
                      className={`text-[10px] px-1.5 py-1 font-medium transition-colors border-r border-border last:border-0 ${
                        active ? 'bg-blue-500/20 text-blue-500' : 'text-muted-foreground hover:bg-secondary'
                      }`}
                    >
                      {style.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        <button
          onClick={handleStart}
          disabled={inProgress || isStarting || selectedPrompts.length === 0}
          className="flex items-center gap-2 px-4 py-1.5 rounded-lg font-medium text-sm transition-all bg-blue-500 hover:bg-blue-600 text-white shadow-md disabled:opacity-50"
        >
          {isStarting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          Start Batch
        </button>
      </div>
    </header>
  )
}

export default BatchHeader
