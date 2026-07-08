import { useState, useEffect, useRef } from 'react'
import { Terminal, Video, RefreshCw, XCircle } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Compiler() {
  const { saveCurrentState } = useAppStore()
  const [filename, setFilename] = useState('')
  const [status, setStatus] = useState('idle') // idle, compiling, complete, error
  const [logs, setLogs] = useState('')
  const [progress, setProgress] = useState(0)
  // Use a ref (not state) for the interval ID to avoid stale-closure and memory-leak issues
  const pollIntervalRef = useRef(null)
  const [badgeText, setBadgeText] = useState('')
  const [showLogs, setShowLogs] = useState(false)
  const logScrollRef = useRef(null) // For auto-scrolling the log pane

  // Cleanup polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [])

  // Auto-scroll log pane to bottom whenever logs update
  useEffect(() => {
    if (logScrollRef.current) {
      logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight
    }
  }, [logs])

  const startPolling = () => {
    let lastLogLength = 0
    
    const interval = setInterval(async () => {
      try {
        const data = await api.getCompilationStatus()
        
        if (data.logs && data.logs.length < lastLogLength) {
          lastLogLength = 0
        }
        if (data.logs && data.logs.length > lastLogLength) {
          lastLogLength = data.logs.length
          setLogs(data.logs)
        }
        
        const logsText = data.logs || ''
        let currentProgress = 10
        let text = 'Starting...'

        if (logsText.includes('Generating voice for chunk')) {
          text = 'Generating Audio...'
          currentProgress = 25
          const matches = logsText.match(/chunk (\d+)\/(\d+)/g)
          if (matches && matches.length > 0) {
            const numMatch = matches[matches.length - 1].match(/chunk (\d+)\/(\d+)/)
            if (numMatch) {
              const current = parseInt(numMatch[1])
              const total = parseInt(numMatch[2])
              currentProgress = 25 + Math.floor((current / total) * 20)
            }
          }
        }
        if (logsText.includes('Transcribing full audio file') || logsText.includes('Transcribing audio...')) {
          text = 'Transcribing Audio...'
          const transMatch = logsText.match(/Transcribing audio\.\.\. (\d+)%/)
          if (transMatch) {
            currentProgress = 45 + Math.floor((parseInt(transMatch[1]) / 100) * 10)
          } else {
            currentProgress = 45
          }
        }
        if (logsText.includes('[3/4]') || logsText.includes('ASS subtitles generated')) {
          currentProgress = 55
          text = 'Generating Subtitles...'
        }
        if (logsText.includes('[4/4]') || logsText.includes('Rendering vertical video')) {
          currentProgress = 70
          text = 'Rendering Video...'
        }
        if (logsText.includes('frame=')) {
          currentProgress = 85
          text = 'Rendering Video...'
        }
        if (logsText.includes('RENDER SUCCESSFUL')) {
          currentProgress = 100
          text = 'Complete!'
        }

        if (data.queue_size && data.queue_size > 0) {
          text += ` (Queue: ${data.queue_size})`
        }

        setProgress(currentProgress)
        setBadgeText(text)

        if (!data.in_progress) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
          
          if (data.success) {
            setProgress(100)
            setBadgeText('Complete!')
            setStatus('complete')
          } else {
            setStatus('error')
          }
        }
      } catch (err) {
        console.error("Polling error", err)
      }
    }, 1000)
    
    pollIntervalRef.current = interval
  }

  const handleCompile = async () => {
    // Prevent double-click before the first render flush clears pollIntervalRef
    if (pollIntervalRef.current) return
    try {
      await saveCurrentState()
      setStatus('compiling')
      setProgress(10)
      setBadgeText('Starting...')
      setLogs('[System Log] Triggering compilation thread on backend...\n')
      
      const res = await api.startCompilation(filename)
      // startCompilation uses raw fetch — check response before starting poll
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(errData.detail || `Compilation failed to start (HTTP ${res.status})`)
      }
      setLogs(prev => prev + '[System Log] Background compilation worker spawned successfully.\n')
      startPolling()
    } catch (err) {
      console.error(err)
      setStatus('error')
      setLogs(prev => prev + `\nError starting compilation: ${err.message}`)
    }
  }

  const handleCancel = async () => {
    try {
      await api.cancelCompilation()
      setLogs(prev => prev + '\n[System Log] Cancel request sent.')
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-3xl mx-auto">
      <div className="text-center space-y-2 mb-8">
        <h2 className="text-2xl font-bold flex items-center justify-center gap-2">
          <Video className="text-emerald-500" />
          Compiler & Live Stream
        </h2>
        <p className="text-muted-foreground text-sm">Review your settings and compile the final video.</p>
      </div>

      <div className="bg-card border border-border rounded-xl p-6 shadow-sm flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-foreground">Custom Output Filename (Optional)</label>
          <input 
            type="text" 
            placeholder="e.g. funny_science.mp4"
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            value={filename}
            onChange={e => setFilename(e.target.value)}
            disabled={status === 'compiling'}
          />
        </div>

        <button 
          onClick={handleCompile}
          disabled={status === 'compiling'}
          className="w-full flex flex-col items-center justify-center gap-1 py-4 rounded-lg transition-all bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white shadow-lg shadow-emerald-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="text-lg font-bold tracking-wide">Compile Short Video</span>
          <span className="text-xs font-medium text-emerald-100 opacity-90">Compiles audio, video, auto-downloads, and burns subtitles.</span>
        </button>

        {status !== 'idle' && (
          <div className="bg-secondary/30 border border-border rounded-lg p-5 flex flex-col gap-4 animate-in fade-in">
            <div className="flex items-center justify-between">
              <span className="px-3 py-1 bg-background border border-border rounded-full text-sm font-semibold flex items-center gap-2 shadow-sm">
                {status === 'compiling' && <RefreshCw size={14} className="animate-spin text-blue-500" />}
                {status === 'complete' && <Video size={14} className="text-emerald-500" />}
                {status === 'error' && <XCircle size={14} className="text-red-500" />}
                {badgeText || (status === 'error' ? 'Failed' : 'Ready')}
              </span>
              
              {status === 'compiling' && (
                <button 
                  onClick={handleCancel}
                  className="px-3 py-1 text-red-500 hover:bg-red-500/10 rounded-md text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>

            <div className="w-full bg-secondary rounded-full h-2.5 overflow-hidden border border-border">
              <div 
                className={cn(
                  "h-full transition-all duration-500 ease-out",
                  status === 'error' ? 'bg-red-500' : 'bg-emerald-500'
                )}
                style={{ width: `${progress}%` }}
              ></div>
            </div>

            <button 
              onClick={() => setShowLogs(!showLogs)}
              className="text-xs text-muted-foreground hover:text-foreground font-medium underline underline-offset-2 transition-colors self-start"
            >
              {showLogs ? 'Hide Detailed Logs' : 'View Detailed Logs'}
            </button>

            {showLogs && (
              <div ref={logScrollRef} className="bg-black/90 text-green-400 font-mono text-xs p-4 rounded-md h-64 overflow-y-auto mt-2 border border-border/50 shadow-inner whitespace-pre-wrap">
                <div className="flex items-center gap-2 text-white/50 border-b border-white/10 pb-2 mb-2 sticky top-0 bg-black/90">
                  <Terminal size={14} />
                  <span>Compilation Console</span>
                </div>
                {logs || '[Waiting for output...]'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
