import { X } from 'lucide-react'
import TikTokIcon from './TikTokIcon'

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200 p-4">
      <div className="bg-card border border-border w-full max-w-md rounded-xl shadow-2xl overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border bg-secondary/30">
          <h3 className="font-semibold flex items-center gap-2">
            <TikTokIcon size={18} className="text-pink-500" />
            Upload to TikTok
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={20} />
          </button>
        </div>
        <div className="p-4 space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">Video File</label>
            <div className="text-sm text-muted-foreground bg-secondary/50 p-2 rounded truncate">
              {video?.filename}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Description & Hashtags</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-background border border-border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm min-h-[120px]"
              placeholder="Enter description and tags..."
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Visibility</label>
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm"
            >
              <option value="Public">Public</option>
              <option value="Friends">Friends Only</option>
              <option value="Private">Private</option>
            </select>
          </div>
        </div>
        <div className="p-4 border-t border-border bg-secondary/30 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-medium text-sm transition-colors hover:bg-secondary border border-border"
          >
            Cancel
          </button>
          <button
            onClick={onUpload}
            disabled={isUploading}
            className="px-6 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-medium text-sm shadow-md transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isUploading ? "Starting..." : "Post to TikTok"}
          </button>
        </div>
      </div>
    </div>
  )
}
