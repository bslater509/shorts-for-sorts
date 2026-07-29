import { X, Music } from 'lucide-react'
import TikTokIcon from './TikTokIcon'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'

export default function TikTokUploadModal({
  isOpen,
  video,
  onClose,
  onUpload,
  isUploading,
  description,
  setDescription,
  visibility,
  setVisibility,
}) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-md animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-gradient-to-b from-card to-card/95 border border-border/60 rounded-2xl shadow-2xl shadow-black/40 max-h-[90dvh] overflow-y-auto flex flex-col">
          {/* ── Header ── */}
          <div className="flex items-center justify-between p-4 border-b border-border/30">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-pink-500/15 flex items-center justify-center ring-1 ring-pink-500/20">
                <TikTokIcon size={16} className="text-pink-400" />
              </div>
              <div>
                <h3 className="font-semibold text-sm text-foreground">Upload to TikTok</h3>
                <p className="text-[11px] text-muted-foreground/60">Post this short to your TikTok account</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary/50"
            >
              <X size={16} />
            </Button>
          </div>

          {/* ── Body ── */}
          <div className="p-4 space-y-4">
            {/* Video File */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-foreground/80 tracking-wide uppercase">
                Video File
              </Label>
              <div className="flex items-center gap-2.5 bg-secondary/20 border border-border/30 rounded-xl p-3">
                <div className="w-9 h-[61px] rounded-lg bg-black/40 overflow-hidden flex-shrink-0 flex items-center justify-center ring-1 ring-white/5">
                  <Music size={14} className="text-muted-foreground/40" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground/90 truncate">
                    {video?.filename}
                  </p>
                  <p className="text-[11px] text-muted-foreground/60 mt-0.5">
                    Vertical short ready for upload
                  </p>
                </div>
              </div>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-foreground/80 tracking-wide uppercase">
                Description &amp; Hashtags
              </Label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-background/50 border border-border/50 rounded-xl p-3.5 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-pink-500/40 focus:ring-2 focus:ring-pink-500/15 transition-all resize-none min-h-[120px]"
                placeholder="Add a caption, mentions, and hashtags..."
              />
            </div>

            {/* Visibility */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-foreground/80 tracking-wide uppercase">
                Visibility
              </Label>
              <Select value={visibility} onValueChange={setVisibility}>
                <SelectTrigger className="w-full bg-background/50 border border-border/50 rounded-xl px-3.5 py-2.5 text-sm text-foreground focus:outline-none focus:border-pink-500/40 focus:ring-2 focus:ring-pink-500/15 transition-all shadow-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Public">Public</SelectItem>
                  <SelectItem value="Friends">Friends Only</SelectItem>
                  <SelectItem value="Private">Private</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* ── Footer ── */}
          <div className="p-4 border-t border-border/30 flex items-center justify-end gap-2.5">
            <Button
              variant="ghost"
              onClick={onClose}
              className="h-9 px-4 rounded-xl text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-all"
            >
              Cancel
            </Button>
            <Button
              variant="default"
              onClick={onUpload}
              disabled={isUploading}
              className="h-9 px-5 rounded-xl bg-pink-500 hover:bg-pink-600 text-white text-sm font-semibold shadow-lg shadow-pink-500/20 disabled:opacity-50 disabled:shadow-none flex items-center gap-2 transition-all"
            >
              {isUploading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Starting...
                </>
              ) : (
                <>
                  <TikTokIcon size={14} />
                  Post to TikTok
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
