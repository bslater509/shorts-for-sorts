import { useState, useEffect } from 'react'
import { Sparkles, Loader2, Bot } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import * as api from '@/lib/api'

export default function ScriptGenerator() {
  const { appState, updateAppState, voices, saveCurrentState } = useAppStore()
  const [prompt, setPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  
  // Use local state for the text area to prevent sluggish typing if Zustand is too global
  const [localScript, setLocalScript] = useState(appState.script_text || '')

  useEffect(() => {
    setLocalScript(appState.script_text || '')
  }, [appState.script_text])

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    
    setIsGenerating(true)
    try {
      const data = await api.generateScript(prompt, appState.selected_voice, null)
      updateAppState({ script_text: data.script })
      await saveCurrentState()
    } catch (err) {
      console.error("Failed to generate script:", err)
      // TODO: implement toast
      alert(`Generation Failed: ${err.message}`)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleScriptChange = (e) => {
    setLocalScript(e.target.value)
  }

  const handleScriptBlur = async () => {
    if (localScript !== appState.script_text) {
      updateAppState({ script_text: localScript })
      await saveCurrentState()
    }
  }

  const wordCount = localScript.trim() ? localScript.trim().split(/\s+/).length : 0

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2 mb-4">
          <Bot className="text-blue-500" />
          AI Script Generator
        </h2>
        
        <div className="bg-secondary/50 rounded-xl p-4 border border-border flex flex-col gap-4">
          <textarea 
            placeholder="Type a viral idea, topic or prompt... (e.g. '3 creepy space mysteries that will keep you awake')"
            className="w-full bg-background border border-border rounded-lg p-3 text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <label className="text-sm font-medium text-muted-foreground whitespace-nowrap">Voice Override</label>
              <select 
                className="bg-background border border-border rounded-md px-3 py-1.5 text-sm w-full sm:w-48 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={appState.selected_voice || ''}
                onChange={async (e) => {
                  updateAppState({ selected_voice: e.target.value, loaded_preset_name: null })
                  await saveCurrentState()
                }}
              >
                <option value="">Default/Current</option>
                {voices.map(v => (
                  <option key={v.value} value={v.value}>{v.name}</option>
                ))}
              </select>
            </div>
            
            <button 
              onClick={handleGenerate}
              disabled={isGenerating || !prompt.trim()}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2 rounded-md font-medium text-sm transition-all bg-blue-500 hover:bg-blue-600 text-white shadow-md shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isGenerating ? 'Generating...' : 'Generate Script'}
            </button>
          </div>
        </div>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border"></div>
        </div>
        <div className="relative flex justify-center">
          <span className="bg-card px-2 text-sm text-muted-foreground">Workspace</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-foreground">Script Content (Spoken Words Only)</label>
          <span className="text-xs font-medium text-muted-foreground bg-secondary px-2 py-1 rounded-md">{wordCount} words</span>
        </div>
        <textarea 
          placeholder="Script content here... If generating, this updates automatically. You can edit directly."
          className="w-full bg-background border border-border rounded-lg p-4 text-sm min-h-[250px] font-medium leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-y shadow-inner"
          value={localScript}
          onChange={handleScriptChange}
          onBlur={handleScriptBlur}
        />
      </div>
    </div>
  )
}
