import os

print("Patching SystemStatsCharts.jsx")
filepath = "gui/frontend/src/components/batch/SystemStatsCharts.jsx"
with open(filepath, "r") as f:
    content = f.read()
content = content.replace(
    "const [collapsed, setCollapsed] = useState(false)",
    "const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768)"
)
with open(filepath, "w") as f:
    f.write(content)

print("Patching JobDetailModal.jsx")
filepath = "gui/frontend/src/components/batch/JobDetailModal.jsx"
with open(filepath, "r") as f:
    content = f.read()
content = content.replace(
    '<div className="flex items-center gap-3">',
    '<div className="flex flex-wrap items-center gap-3">'
)
content = content.replace(
    '<FolderOpen size={13} />\n                Open Folder',
    '<FolderOpen size={13} />\n                <span className="hidden sm:inline">Open Folder</span>'
)
with open(filepath, "w") as f:
    f.write(content)

print("Patching Batch.jsx")
filepath = "gui/frontend/src/pages/Batch.jsx"
with open(filepath, "r") as f:
    content = f.read()
content = content.replace(
    '"px-2.5 py-1 text-[10px] md:text-xs font-medium rounded-md border transition-colors whitespace-nowrap"',
    '"px-2.5 py-1 min-h-[36px] md:min-h-[28px] text-[10px] md:text-xs font-medium rounded-md border transition-colors whitespace-nowrap flex items-center"'
)
content = content.replace(
    'max-w-6xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)]"',
    'max-w-6xl mx-auto flex flex-col min-h-0 md:min-h-[calc(100dvh-6rem)] pb-28 md:pb-0"'
)

sticky_bar = """
      {/* Mobile Sticky Action Bar */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-card/95 backdrop-blur-md border-t border-border p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.1)]">
        <Button
          variant="default"
          onClick={inProgress ? handleCancel : handleStart}
          disabled={isStarting || (!inProgress && selectedPrompts.length === 0)}
          className={`w-full flex items-center justify-center gap-2 py-6 rounded-xl font-bold text-sm shadow-md transition-all duration-200 ${
            inProgress
              ? 'bg-red-500 hover:bg-red-600 text-white shadow-red-500/25'
              : !isStarting && selectedPrompts.length > 0
                ? 'bg-blue-500 hover:bg-blue-600 text-white shadow-blue-500/25'
                : ''
          }`}
        >
          {isStarting ? (
            <Loader2 size={16} className="animate-spin" />
          ) : inProgress ? (
            <Square size={16} />
          ) : (
            <Play size={16} />
          )}
          {isStarting ? 'Starting...' : inProgress ? 'Cancel Batch' : 'Start Batch'}
        </Button>
      </div>
"""

if "    </div>\n  )\n}" in content:
    content = content.replace("    </div>\n  )\n}", sticky_bar + "\n    </div>\n  )\n}")
else:
    print("Could not find insertion point in Batch.jsx")
with open(filepath, "w") as f:
    f.write(content)

print("Patching BatchHeader.jsx")
filepath = "gui/frontend/src/components/batch/BatchHeader.jsx"
with open(filepath, "r") as f:
    content = f.read()

imports_addition = """
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { ChevronUp, Settings2 } from 'lucide-react'
"""
content = content.replace("import { Layers, ChevronDown,", imports_addition + "import { Layers, ChevronDown,")

parts = content.split("  return (")
header = parts[0]
return_stmt = "  return (" + parts[1]

new_return_stmt = """  return (
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
              <PromptSelectorContent />
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
              <EmojiSettingsContent />
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
               <ProfilesContent />
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
                onClick={() => {
                  setProfilesOpen(true)
                  fetchProfiles()
                }}
                disabled={inProgress}
                className="w-full flex items-center justify-between col-span-2 gap-1 bg-background border border-border rounded-lg px-3 py-2 text-xs font-medium hover:bg-secondary/50 disabled:opacity-50 h-auto min-h-[44px] shadow-sm"
              >
                <span className="flex items-center gap-1.5 truncate">
                  <FolderOpen size={14} className="flex-shrink-0" />
                  <span className="truncate">{selectedProfile || 'Load / Save Profiles'}</span>
                </span>
                <ChevronDown size={14} className="opacity-50 flex-shrink-0" />
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
           <PromptSelectorContent />
        </div>
      </BottomSheet>
      
      <BottomSheet 
        isOpen={emojiPopoverOpen && typeof window !== 'undefined' && window.innerWidth < 768} 
        onClose={() => setEmojiPopoverOpen(false)} 
        title="Emoji Settings"
      >
        <EmojiSettingsContent />
      </BottomSheet>

      <BottomSheet 
        isOpen={profilesOpen && typeof window !== 'undefined' && window.innerWidth < 768} 
        onClose={() => setProfilesOpen(false)} 
        title="Batch Profiles"
      >
        <ProfilesContent />
      </BottomSheet>

    </header>
  )
"""

new_code = header + """
  const [mobileOptionsOpen, setMobileOptionsOpen] = useState(false)

  const PromptSelectorContent = () => (
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

  const EmojiSettingsContent = () => (
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

  const ProfilesContent = () => (
    <>
      <div className="p-3 md:p-2 border-b border-border bg-secondary/30">
        <p className="text-xs md:text-[10px] font-semibold text-muted-foreground mb-2 md:mb-1.5 hidden md:block">Batch Profiles</p>
        {profiles.length > 0 && (
          <div className="max-h-48 md:max-h-36 overflow-y-auto space-y-1 md:space-y-0.5 mb-2">
            {profiles.map((p) => (
              <div key={p.name} className="flex items-center justify-between gap-2 rounded hover:bg-secondary/50 px-2 md:px-1.5 py-2 md:py-1">
                <button
                  onClick={() => { handleLoadProfile(p.name); setProfilesOpen(false) }}
                  className={`text-sm md:text-[11px] text-left flex-1 truncate ${
                    selectedProfile === p.name ? 'text-blue-400 font-semibold' : 'text-foreground'
                  }`}
                >
                  {p.name}
                </button>
                <button
                  onClick={() => handleDeleteProfile(p.name)}
                  className="text-muted-foreground hover:text-red-400 transition-colors p-1 md:p-0.5"
                >
                  <Trash2 size={14} className="md:w-2.5 md:h-2.5" />
                </button>
              </div>
            ))}
          </div>
        )}
        {profilesLoading && <p className="text-xs md:text-[10px] text-muted-foreground text-center py-2 md:py-1">Loading...</p>}
      </div>
      <div className="p-3 md:p-2 space-y-2 md:space-y-1.5">
        <Input
          value={profileNameInput}
          onChange={(e) => setProfileNameInput(e.target.value)}
          placeholder="New profile name..."
          className="h-9 md:h-7 text-xs md:text-[11px] px-3 md:px-2 py-1.5 md:py-1"
          onKeyDown={(e) => { if (e.key === 'Enter') handleSaveProfile() }}
        />
        <Button
          variant="outline"
          onClick={handleSaveProfile}
          disabled={savingProfile || !profileNameInput.trim()}
          className="w-full text-xs md:text-[10px] h-9 md:h-7 px-3 md:px-2 flex items-center justify-center gap-1.5 md:gap-1"
        >
          {savingProfile ? <Loader2 size={12} className="animate-spin md:w-2.5 md:h-2.5" /> : <Save size={12} className="md:w-2.5 md:h-2.5" />}
          Save Current Config
        </Button>
      </div>
    </>
  )

""" + new_return_stmt + "\n}\n\nexport default BatchHeader\n"

with open(filepath, "w") as f:
    f.write(new_code)
