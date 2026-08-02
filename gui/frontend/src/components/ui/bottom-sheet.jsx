import * as React from "react"
import { X } from "lucide-react"

/** 
 * UI/UX Rationale: 
 * Mobile users need large tap targets and contextual menus that don't overflow small screens.
 * This bottom sheet provides a standard slide-up pattern for mobile dropdown replacements.
 */
export function BottomSheet({ isOpen, onClose, title, children }) {
  React.useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    if (isOpen) window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="md:hidden">
      <div 
        className="fixed inset-0 bg-black/60 z-50 animate-in fade-in duration-200" 
        onClick={onClose} 
      />
      <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl border-t border-border bg-card max-h-[85vh] flex flex-col shadow-[0_-8px_30px_rgba(0,0,0,0.4)] animate-in slide-in-from-bottom duration-300">
        <div className="flex-shrink-0 flex flex-col items-center pt-2 pb-1">
          <div className="w-12 h-1.5 bg-muted rounded-full" />
        </div>
        <div className="flex-shrink-0 flex items-center justify-between px-4 pb-3 border-b border-border/50">
          <h3 className="text-base font-bold text-foreground">{title}</h3>
          <button 
            onClick={onClose} 
            className="p-1.5 rounded-full hover:bg-secondary/80 text-muted-foreground transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div className="overflow-y-auto p-4 flex-1 overscroll-contain pb-[calc(1rem+env(safe-area-inset-bottom))]">
          {children}
        </div>
      </div>
    </div>
  )
}
