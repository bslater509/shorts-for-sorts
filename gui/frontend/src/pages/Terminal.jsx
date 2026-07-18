import { useEffect, useRef, useState } from 'react'
import { Terminal as TerminalIcon, XCircle, SkipBack, SkipForward, Folder, Monitor, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ScrollText, ChevronsUp, ChevronsDown, Sun, Loader2, WifiOff, PlusSquare, Settings, Trash2, Plus, X, Palette } from 'lucide-react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import NoSleep from 'nosleep.js'
import '@xterm/xterm/css/xterm.css'

const TERMINAL_THEMES = {
  default: {
    name: 'Default Dark',
    theme: {
      background: '#0b0814',
      foreground: '#e4e2f0',
      cursor: '#9d4edd',
      cursorAccent: '#0b0814',
      selectionBackground: '#9d4edd44',
      black: '#1a1525',
      red: '#e06c75',
      green: '#98c379',
      yellow: '#e5c07b',
      blue: '#61afef',
      magenta: '#c678dd',
      cyan: '#56b6c2',
      white: '#abb2bf',
      brightBlack: '#4a4358',
      brightRed: '#ff6b7d',
      brightGreen: '#a9dd8a',
      brightYellow: '#fbd38d',
      brightBlue: '#7cb8f7',
      brightMagenta: '#d68deb',
      brightCyan: '#6bd6e0',
      brightWhite: '#e4e2f0',
    }
  },
  dracula: {
    name: 'Dracula',
    theme: {
      background: '#282a36',
      foreground: '#f8f8f2',
      cursor: '#f8f8f2',
      cursorAccent: '#282a36',
      selectionBackground: '#44475a',
      black: '#21222c',
      red: '#ff5555',
      green: '#50fa7b',
      yellow: '#f1fa8c',
      blue: '#bd93f9',
      magenta: '#ff79c6',
      cyan: '#8be9fd',
      white: '#f8f8f2',
      brightBlack: '#6272a4',
      brightRed: '#ff6e6e',
      brightGreen: '#69ff94',
      brightYellow: '#ffffa5',
      brightBlue: '#d6acff',
      brightMagenta: '#ff92df',
      brightCyan: '#a4ffff',
      brightWhite: '#ffffff'
    }
  },
  nord: {
    name: 'Nord',
    theme: {
      background: '#2E3440',
      foreground: '#D8DEE9',
      cursor: '#D8DEE9',
      cursorAccent: '#2E3440',
      selectionBackground: '#434C5E',
      black: '#3B4252',
      red: '#BF616A',
      green: '#A3BE8C',
      yellow: '#EBCB8B',
      blue: '#81A1C1',
      magenta: '#B48EAD',
      cyan: '#88C0D0',
      white: '#E5E9F0',
      brightBlack: '#4C566A',
      brightRed: '#BF616A',
      brightGreen: '#A3BE8C',
      brightYellow: '#EBCB8B',
      brightBlue: '#81A1C1',
      brightMagenta: '#B48EAD',
      brightCyan: '#8FBCBB',
      brightWhite: '#ECEFF4'
    }
  },
  ubuntu: {
    name: 'Ubuntu',
    theme: {
      background: '#300a24',
      foreground: '#eeeeee',
      cursor: '#eeeeee',
      cursorAccent: '#300a24',
      selectionBackground: '#773865',
      black: '#2e3436',
      red: '#cc0000',
      green: '#4e9a06',
      yellow: '#c4a000',
      blue: '#3465a4',
      magenta: '#75507b',
      cyan: '#06989a',
      white: '#d3d7cf',
      brightBlack: '#555753',
      brightRed: '#ef2929',
      brightGreen: '#8ae234',
      brightYellow: '#fce94f',
      brightBlue: '#729fcf',
      brightMagenta: '#ad7fa8',
      brightCyan: '#34e2e2',
      brightWhite: '#eeeeee'
    }
  }
}

export default function TerminalPage() {
  const [isAwake, setIsAwake] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState('connecting')
  const [commandInput, setCommandInput] = useState('')
  const [activeCommand, setActiveCommand] = useState('')
  
  // History & Snippets State
  const [commandHistory, setCommandHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [savedDraft, setSavedDraft] = useState('')
  const [customSnippets, setCustomSnippets] = useState([])
  const [isSnippetsModalOpen, setIsSnippetsModalOpen] = useState(false)
  const [newSnippetName, setNewSnippetName] = useState('')
  const [newSnippetCommand, setNewSnippetCommand] = useState('')

  // Appearance State
  const [isAppearanceModalOpen, setIsAppearanceModalOpen] = useState(false)
  const [terminalSettings, setTerminalSettings] = useState({
    fontSize: 10,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Monaco', monospace",
    cursorStyle: 'bar',
    cursorBlink: true,
    themeName: 'default'
  })

  const reconnectAttemptRef = useRef(0)
  const isInitialConnectionRef = useRef(true)
  const noSleepRef = useRef(null)

  const updateTerminalSettings = (newSettings) => {
    setTerminalSettings(newSettings)
    localStorage.setItem('terminalAppearanceSettings', JSON.stringify(newSettings))
    if (xtermRef.current) {
      xtermRef.current.options.fontSize = parseInt(newSettings.fontSize) || 10
      xtermRef.current.options.fontFamily = newSettings.fontFamily
      xtermRef.current.options.cursorStyle = newSettings.cursorStyle
      xtermRef.current.options.cursorBlink = newSettings.cursorBlink
      if (TERMINAL_THEMES[newSettings.themeName]) {
        xtermRef.current.options.theme = TERMINAL_THEMES[newSettings.themeName].theme
      }
      fitAddonRef.current?.fit()
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'resize', cols: xtermRef.current.cols, rows: xtermRef.current.rows }))
      }
    }
  }

  const saveSnippets = (snippets) => {
    setCustomSnippets(snippets)
    localStorage.setItem('terminalCustomSnippets', JSON.stringify(snippets))
  }

  const addSnippet = () => {
    if (newSnippetName.trim() && newSnippetCommand.trim()) {
      const newSnippet = {
        id: Date.now().toString(),
        name: newSnippetName.trim(),
        command: newSnippetCommand
      }
      saveSnippets([...customSnippets, newSnippet])
      setNewSnippetName('')
      setNewSnippetCommand('')
    }
  }

  const removeSnippet = (id) => {
    saveSnippets(customSnippets.filter(s => s.id !== id))
  }

  const sendCommand = () => {
    if (commandInput && sendInputRef.current) {
      sendInputRef.current(commandInput + '\r')
      
      setCommandHistory(prev => {
        const newHistory = [...prev]
        if (newHistory.length === 0 || newHistory[newHistory.length - 1] !== commandInput) {
          newHistory.push(commandInput)
        }
        if (newHistory.length > 100) newHistory.shift()
        localStorage.setItem('terminalCommandHistory', JSON.stringify(newHistory))
        return newHistory
      })
      setHistoryIndex(-1)
      setSavedDraft('')

      setCommandInput('')
      if (inputRef.current) {
        inputRef.current.style.height = 'auto'
      }
    }
  }

  useEffect(() => {
    noSleepRef.current = new NoSleep()
    try {
      const savedHistory = localStorage.getItem('terminalCommandHistory')
      if (savedHistory) setCommandHistory(JSON.parse(savedHistory))
      
      const savedSnippets = localStorage.getItem('terminalCustomSnippets')
      if (savedSnippets) setCustomSnippets(JSON.parse(savedSnippets))
    } catch (e) {
      console.error('Failed to load terminal local storage data:', e)
    }

    return () => {
      if (noSleepRef.current) {
        noSleepRef.current.disable()
      }
    }
  }, [])

  const toggleWakeLock = async () => {
    if (isAwake) {
      if (noSleepRef.current) {
        noSleepRef.current.disable()
      }
      setIsAwake(false)
    } else {
      if (noSleepRef.current) {
        try {
          await noSleepRef.current.enable()
          setIsAwake(true)
        } catch (err) {
          console.error('NoSleep error:', err)
          alert('Could not enable wake lock.')
        }
      }
    }
  }


  const containerRef = useRef(null)
  const xtermRef = useRef(null)
  const wsRef = useRef(null)
  const fitAddonRef = useRef(null)
  const sendInputRef = useRef(null)
  const inputRef = useRef(null)

  const handleSlashCommand = (cmd) => {
    const trimmedCmd = cmd.trim();
    if (trimmedCmd === '/new') {
      if (sendInputRef.current) {
        sendInputRef.current(trimmedCmd + '\r');
      }
    } else {
      const currentText = commandInput.trim();
      const newText = currentText ? `${trimmedCmd} ${currentText}` : `${trimmedCmd} `;
      setCommandInput(newText);
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          const length = inputRef.current.value.length;
          inputRef.current.setSelectionRange(length, length);
        }
      }, 0);
    }
  }

  useEffect(() => {
    let initialSettings = {
      fontSize: 10,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Monaco', monospace",
      cursorStyle: 'bar',
      cursorBlink: true,
      themeName: 'default'
    }
    try {
      const savedAppearance = localStorage.getItem('terminalAppearanceSettings')
      if (savedAppearance) {
        initialSettings = { ...initialSettings, ...JSON.parse(savedAppearance) }
        setTerminalSettings(initialSettings)
      }
    } catch(e) {
      console.error('Failed to load appearance settings:', e)
    }

    const term = new XTerm({
      cursorBlink: initialSettings.cursorBlink,
      cursorStyle: initialSettings.cursorStyle,
      fontSize: initialSettings.fontSize,
      fontFamily: initialSettings.fontFamily,
      theme: TERMINAL_THEMES[initialSettings.themeName]?.theme || TERMINAL_THEMES['default'].theme,
      allowProposedApi: true,
      allowTransparency: false,
      scrollback: 5000,
      tabStopWidth: 4,
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    xtermRef.current = term
    fitAddonRef.current = fitAddon

    if (containerRef.current) {
      term.open(containerRef.current)
      fitAddon.fit()
    }

    let reconnectTimeout = null

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/terminal`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnectionStatus('connected')
        reconnectAttemptRef.current = 0
        fitAddon.fit()
        
        if (isInitialConnectionRef.current) {
          term.clear()
          term.writeln('\x1b[1;35m  ShortsCreator Terminal\x1b[0m')
          term.writeln('\x1b[2m  ──────────────────────────\x1b[0m')
          term.writeln('')
        } else {
          term.writeln('\r\n\x1b[32m  Reconnected successfully.\x1b[0m')
        }

        // Signal terminal size to the backend
        ws.send(
          JSON.stringify({
            type: 'resize',
            cols: term.cols,
            rows: term.rows,
          })
        )
        
        const pollInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'get_active_command' }))
          }
        }, 1000)
        
        ws.addEventListener('close', () => clearInterval(pollInterval))

        isInitialConnectionRef.current = false
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'output') {
            term.write(msg.data)
          } else if (msg.type === 'active_command') {
            setActiveCommand(msg.data)
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        // Will be handled by onclose
      }

      ws.onclose = () => {
        handleReconnect()
      }
    }

    const handleReconnect = () => {
      setConnectionStatus('reconnecting')
      const baseDelay = 1000
      const maxDelay = 10000
      const delay = Math.min(baseDelay * Math.pow(1.5, reconnectAttemptRef.current), maxDelay)
      reconnectAttemptRef.current += 1

      reconnectTimeout = setTimeout(() => {
        connect()
      }, delay)
    }

    connect()

    // Forward keyboard input to WebSocket
    const send = (data) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }))
      }
    }
    sendInputRef.current = send
    const dataDisposable = term.onData((data) => send(data))

    // Resize handling
    const handleResize = () => {
      fitAddon.fit()
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'resize',
            cols: term.cols,
            rows: term.rows,
          })
        )
      }
    }

    let resizeTimer = null
    const resizeObserver = new ResizeObserver(() => {
      clearTimeout(resizeTimer)
      resizeTimer = setTimeout(handleResize, 100)
    })

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current)
    }

    // Fallback: also listen to window resize
    window.addEventListener('resize', handleResize)

    return () => {
      clearTimeout(reconnectTimeout)
      window.removeEventListener('resize', handleResize)
      resizeObserver.disconnect()
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect loop on unmount
        wsRef.current.close()
      }
      dataDisposable.dispose()
      term.dispose()
    }
  }, [])

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 w-full flex flex-col md:h-[calc(100dvh-73px)] lg:h-screen md:space-y-0">
      <header className="shrink-0 hidden md:block">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <TerminalIcon className="text-blue-500" />
          Terminal
        </h1>
        <p className="text-muted-foreground mt-1">
          Direct shell access on the server. tmux, git, pip, npm — anything you need.
        </p>
      </header>

      <div className="bg-card border-0 md:border md:border-border rounded-none md:rounded-xl overflow-hidden shadow-none md:shadow-lg flex flex-col relative md:flex-1 md:min-h-0 shrink-0">
        {(connectionStatus === 'reconnecting' || connectionStatus === 'connecting') && (
          <div className="absolute inset-0 bg-background/50 backdrop-blur-sm z-10 flex flex-col items-center justify-center pointer-events-none">
            <div className="bg-card border border-border rounded-lg shadow-xl p-4 flex items-center gap-3 animate-in zoom-in-95 duration-200">
              {connectionStatus === 'reconnecting' ? (
                <>
                  <WifiOff className="text-yellow-500 animate-pulse" size={20} />
                  <span className="text-sm font-medium text-foreground">Connection lost. Reconnecting...</span>
                </>
              ) : (
                <>
                  <Loader2 className="text-blue-500 animate-spin" size={20} />
                  <span className="text-sm font-medium text-foreground">Connecting to terminal...</span>
                </>
              )}
            </div>
          </div>
        )}
        <div
          ref={containerRef}
          className="w-full h-[600px] md:h-auto md:flex-1 relative bg-[#0b0814] overflow-hidden shrink-0 md:shrink md:min-h-0"
          style={{ padding: '0px' }}
        />
        
        <div className="flex items-end gap-2 p-1 border-t border-border shrink-0 bg-muted/10">
          <textarea
            ref={inputRef}
            rows={1}
            placeholder="Type a command and press Enter..."
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            autoCapitalize="none"
            autoComplete="off"
            autoCorrect="off"
            spellCheck="false"
            onInput={(e) => {
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 150)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendCommand()
              } else if (e.key === 'ArrowUp') {
                if (commandHistory.length > 0) {
                  e.preventDefault()
                  let newIndex = historyIndex === -1 ? commandHistory.length - 1 : historyIndex - 1
                  if (newIndex < 0) newIndex = 0
                  
                  if (historyIndex === -1) {
                    setSavedDraft(commandInput)
                  }
                  
                  setHistoryIndex(newIndex)
                  setCommandInput(commandHistory[newIndex])
                }
              } else if (e.key === 'ArrowDown') {
                if (historyIndex !== -1) {
                  e.preventDefault()
                  const newIndex = historyIndex + 1
                  if (newIndex >= commandHistory.length) {
                    setHistoryIndex(-1)
                    setCommandInput(savedDraft)
                  } else {
                    setHistoryIndex(newIndex)
                    setCommandInput(commandHistory[newIndex])
                  }
                }
              }
            }}
            className="flex-1 bg-background border border-input rounded-md px-1 py-0.5 text-base md:text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none overflow-y-auto min-h-[36px] leading-relaxed"
            style={{ boxSizing: 'border-box' }}
          />
        </div>

                        <div className="flex items-center gap-2 p-1 border-t border-border shrink-0 flex-wrap overflow-x-auto bg-muted/10">
          
          {/* SYSTEM BLOCK */}
          <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
            <button
              onClick={toggleWakeLock}
              className={`flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium transition-colors ${isAwake ? 'bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30' : 'bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20'}`}
            >
              <Sun size={16} className={isAwake ? 'animate-pulse' : ''} />
              {isAwake ? 'Awake' : 'Sleep OK'}
            </button>
            <button
              onClick={() => sendInputRef.current?.('cd /mnt/gb250/shorts-for-sorts\r')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <Folder size={16} />
              cd root
            </button>
          </div>

          {/* TMUX BLOCK */}
          <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
            <button
              onClick={() => sendInputRef.current?.('tmux attach\r')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <Monitor size={16} />
              Attach
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02c')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              <PlusSquare size={16} />
              New
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02p')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              <SkipBack size={16} />
              Prev
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02n')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              <SkipForward size={16} />
              Next
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02"')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              Split H
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02%')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              Split V
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02o')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              Cycle
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x02z')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
            >
              Zoom
            </button>
          </div>

          {/* SCROLL BLOCK */}
          <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
            <button
              onClick={() => sendInputRef.current?.('\x02[')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-colors"
            >
              <ScrollText size={16} />
              Mode
            </button>
            <button
              onClick={() => sendInputRef.current?.('q')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-colors"
            >
              Exit
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1b[5~')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ChevronsUp size={16} />
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1b[6~')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ChevronsDown size={16} />
            </button>
          </div>

          {/* KEYS BLOCK */}
          <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
            <button
              onClick={() => sendInputRef.current?.('\x1b')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              Esc
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x03')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <XCircle size={16} />
              Ctrl+C
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1a')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              Ctrl+Z
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x04')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              Ctrl+D
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x0c')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              Ctrl+L
            </button>
            <button
              onClick={() => sendInputRef.current?.('\t')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              Tab
            </button>
            <button
              onClick={() => sendInputRef.current?.(' ')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              Space
            </button>
            <button
              onClick={() => sendInputRef.current?.('x')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              x
            </button>
          </div>

          {/* NAV BLOCK */}
          <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
            <button
              onClick={() => sendInputRef.current?.('\x1b[D')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ArrowLeft size={16} />
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1b[B')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ArrowDown size={16} />
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1b[A')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ArrowUp size={16} />
            </button>
            <button
              onClick={() => sendInputRef.current?.('\x1b[C')}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-zinc-500/10 text-zinc-400 hover:bg-zinc-500/20 transition-colors"
            >
              <ArrowRight size={16} />
            </button>
          </div>

          {/* CUSTOM SNIPPETS BLOCK */}
          {customSnippets.length > 0 && (
            <div className="flex items-center flex-wrap gap-0.5 p-1 rounded-lg bg-background/50 border border-border/50">
              {customSnippets.map(snippet => (
                <button
                  key={snippet.id}
                  onClick={() => sendInputRef.current?.(snippet.command + '\r')}
                  className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 transition-colors"
                >
                  {snippet.name}
                </button>
              ))}
            </div>
          )}
          
          <div className="ml-auto shrink-0 flex items-center gap-1">
            <button
              onClick={() => setIsAppearanceModalOpen(true)}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-muted/50 text-muted-foreground hover:bg-muted transition-colors"
              title="Appearance Settings"
            >
              <Palette size={16} />
            </button>
            <button
              onClick={() => setIsSnippetsModalOpen(true)}
              className="flex items-center justify-center px-1.5 py-0.5 rounded-md text-sm font-medium bg-muted/50 text-muted-foreground hover:bg-muted transition-colors"
              title="Manage Snippets"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>
        {activeCommand === 'agy' && (
          <div className="flex items-center gap-2 p-1 border-t border-border shrink-0 flex-wrap bg-muted/5">
          <button
            onClick={() => handleSlashCommand('/new ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /new
          </button>
          <button
            onClick={() => handleSlashCommand('/goal ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /goal
          </button>
          <button
            onClick={() => handleSlashCommand('/plan ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /plan
          </button>
          <button
            onClick={() => handleSlashCommand('/learn ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /learn
          </button>
          <button
            onClick={() => handleSlashCommand('/schedule ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /schedule
          </button>
          <button
            onClick={() => handleSlashCommand('/grill-me ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /grill-me
          </button>
          <button
            onClick={() => handleSlashCommand('/artifact ')}
            className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors shrink-0"
          >
            /artifact
          </button>
        </div>
        )}
        {activeCommand === 'opencode' && (
          <div className="flex items-center gap-2 p-1 border-t border-border shrink-0 flex-wrap bg-muted/5">
            <button
              onClick={() => handleSlashCommand('/new ')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors shrink-0"
            >
              /new
            </button>
            <button
              onClick={() => handleSlashCommand('/undo ')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors shrink-0"
            >
              /undo
            </button>
            <button
              onClick={() => handleSlashCommand('/retry ')}
              className="flex items-center gap-1.5 px-1.5 py-0.5 rounded-md text-sm font-medium bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors shrink-0"
            >
              /retry
            </button>
          </div>
        )}
      </div>

      {/* APPEARANCE MODAL */}
      {isAppearanceModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Palette size={18} className="text-pink-500" />
                Terminal Appearance
              </h2>
              <button 
                onClick={() => setIsAppearanceModalOpen(false)}
                className="p-1 hover:bg-muted rounded-md text-muted-foreground transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            
            <div className="p-4 flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Theme</label>
                <select
                  value={terminalSettings.themeName}
                  onChange={(e) => updateTerminalSettings({ ...terminalSettings, themeName: e.target.value })}
                  className="w-full bg-background border border-input rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {Object.entries(TERMINAL_THEMES).map(([key, theme]) => (
                    <option key={key} value={key}>{theme.name}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Font Size ({terminalSettings.fontSize}px)</label>
                <input
                  type="range"
                  min="8"
                  max="24"
                  step="1"
                  value={terminalSettings.fontSize}
                  onChange={(e) => updateTerminalSettings({ ...terminalSettings, fontSize: parseInt(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Font Family</label>
                <input
                  type="text"
                  value={terminalSettings.fontFamily}
                  onChange={(e) => updateTerminalSettings({ ...terminalSettings, fontFamily: e.target.value })}
                  className="w-full bg-background border border-input rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring font-mono"
                />
                <p className="text-xs text-muted-foreground">Comma-separated list of font families.</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Cursor Style</label>
                <div className="flex gap-2">
                  {['block', 'underline', 'bar'].map(style => (
                    <button
                      key={style}
                      onClick={() => updateTerminalSettings({ ...terminalSettings, cursorStyle: style })}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${terminalSettings.cursorStyle === style ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
                    >
                      {style}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">Cursor Blink</label>
                <button
                  onClick={() => updateTerminalSettings({ ...terminalSettings, cursorBlink: !terminalSettings.cursorBlink })}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background ${terminalSettings.cursorBlink ? 'bg-primary' : 'bg-input'}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition duration-200 ease-in-out ${terminalSettings.cursorBlink ? 'translate-x-2' : '-translate-x-2'}`}
                  />
                </button>
              </div>
            </div>
            
            <div className="p-4 border-t border-border bg-muted/30 flex justify-end">
              <button
                onClick={() => setIsAppearanceModalOpen(false)}
                className="px-4 py-2 bg-background border border-input rounded-md text-sm font-medium hover:bg-muted transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MANAGE SNIPPETS MODAL */}
      {isSnippetsModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Settings size={18} className="text-indigo-500" />
                Manage Snippets
              </h2>
              <button 
                onClick={() => setIsSnippetsModalOpen(false)}
                className="p-1 hover:bg-muted rounded-md text-muted-foreground transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            
            <div className="p-4 flex flex-col gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Add New Snippet</label>
                <div className="flex flex-col gap-2">
                  <input
                    type="text"
                    placeholder="Label (e.g., 'htop')"
                    value={newSnippetName}
                    onChange={e => setNewSnippetName(e.target.value)}
                    className="flex-1 bg-background border border-input rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Command (e.g., 'htop')"
                      value={newSnippetCommand}
                      onChange={e => setNewSnippetCommand(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && addSnippet()}
                      className="flex-1 bg-background border border-input rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring font-mono"
                    />
                    <button
                      onClick={addSnippet}
                      disabled={!newSnippetName.trim() || !newSnippetCommand.trim()}
                      className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-1"
                    >
                      <Plus size={16} />
                      Add
                    </button>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2 pt-2 border-t border-border">
                <label className="text-sm font-medium text-foreground">Your Snippets</label>
                {customSnippets.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic text-center py-4 bg-muted/30 rounded-md border border-dashed border-border">
                    No custom snippets yet. Add one above!
                  </p>
                ) : (
                  <div className="flex flex-col gap-2 max-h-[40vh] overflow-y-auto pr-1">
                    {customSnippets.map(snippet => (
                      <div key={snippet.id} className="flex items-center justify-between p-2 rounded-md bg-muted/50 border border-border group hover:bg-muted transition-colors">
                        <div className="flex flex-col overflow-hidden">
                          <span className="text-sm font-medium truncate">{snippet.name}</span>
                          <span className="text-xs text-muted-foreground font-mono truncate">{snippet.command}</span>
                        </div>
                        <button
                          onClick={() => removeSnippet(snippet.id)}
                          className="p-1.5 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-md transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                          title="Delete snippet"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            <div className="p-4 border-t border-border bg-muted/30 flex justify-end">
              <button
                onClick={() => setIsSnippetsModalOpen(false)}
                className="px-4 py-2 bg-background border border-input rounded-md text-sm font-medium hover:bg-muted transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
