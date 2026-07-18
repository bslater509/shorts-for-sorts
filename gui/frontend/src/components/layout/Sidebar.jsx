import { NavLink } from "react-router-dom"
import { Wand2, Image as ImageIcon, Sliders, Film, Settings, Layers, Terminal as TerminalIcon, Menu, X, RefreshCw, Loader2 } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"
import { useAppStore } from "@/store/useAppStore"
import SystemStats from "./SystemStats"

export default function Sidebar() {
  const [isOpen, setIsOpen] = useState(false)
  const [restarting, setRestarting] = useState(false)
  const loadedPreset = useAppStore(state => state.appState.loaded_preset_name) || "None (Custom)"

  const navItems = [
    { name: "Studio", path: "/", icon: Wand2 },
    { name: "Media Manager", path: "/media", icon: ImageIcon },
    { name: "Presets", path: "/presets", icon: Sliders },
    { name: "Video Gallery", path: "/gallery", icon: Film },
    { name: "Settings", path: "/settings", icon: Settings },
    { name: "Batch Generator", path: "/batch", icon: Layers },
    { name: "Terminal", path: "/terminal", icon: TerminalIcon },
    { name: "Playground", path: "/playground", icon: Wand2 },
  ]

  const pollServer = (retries = 60, interval = 2000) => {
    let count = 0;
    const poll = () => {
      count++;
      fetch("/api/health", { signal: AbortSignal.timeout(3000) })
        .then(r => r.json())
        .then(() => window.location.reload())
        .catch(() => {
          if (count < retries) setTimeout(poll, interval);
          else { setRestarting(false); alert("Server restart timed out. Please refresh manually."); }
        });
    };
    setTimeout(poll, 8000);
  };

  const handleRestart = async () => {
    if (!window.confirm("Are you sure you want to restart the server? Any ongoing generations will be lost.")) return;
    setRestarting(true);
    try {
      await fetch('/api/restart', { method: 'POST' });
      pollServer();
    } catch (e) {
      console.error(e);
      setRestarting(false);
      alert("Failed to send restart command.");
    }
  }

  return (
    <>
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-card border-b border-border sticky top-0 z-50">
        <span className="font-bold text-lg bg-gradient-to-r from-blue-500 to-blue-400 bg-clip-text text-transparent">
          ShortsCreator
        </span>
        <button onClick={() => setIsOpen(!isOpen)} className="p-2 text-foreground">
          {isOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed md:sticky top-0 left-0 h-screen w-64 bg-card border-r border-border z-50 flex flex-col transition-transform duration-300 ease-in-out md:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="p-6 flex flex-col gap-2 border-b border-border">
          <h2 className="text-2xl font-bold tracking-tight">
            Shorts<span className="text-blue-500">Creator</span>
          </h2>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 flex flex-col gap-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setIsOpen(false)}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive 
                  ? "bg-blue-500/10 text-blue-500" 
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              <item.icon size={20} />
              {item.name}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-border mt-auto">
          <div className="bg-secondary rounded-lg p-3 text-sm">
            <p className="text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-1">Preset Loaded</p>
            <p className="font-medium truncate">{loadedPreset}</p>
          </div>
          <SystemStats />
          <button
            onClick={handleRestart}
            disabled={restarting}
            className="w-full mt-4 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 text-red-400 hover:bg-red-500/10 hover:text-red-500 border border-border hover:border-red-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {restarting ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {restarting ? "Restarting..." : "Restart Server"}
          </button>
        </div>
      </aside>
    </>
  )
}
