import { X } from 'lucide-react'
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200 p-4">
      <div className="bg-card border border-border w-full max-w-md rounded-xl shadow-2xl max-h-[90dvh] overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-border bg-secondary/30">
          <h3 className="font-semibold flex items-center gap-2">
            <TikTokIcon size={18} className="text-pink-500" />
            Upload to TikTok
          </h3>
          <Button variant="ghost" size="icon" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={20} />
          </Button>
        </div>
        <div className="p-4 space-y-4">
          <div className="space-y-1">
            <Label className="text-sm font-medium">Video File</Label>
            <div className="text-sm text-muted-foreground bg-secondary/50 p-2 rounded truncate">
              {video?.filename}
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-sm font-medium">Description & Hashtags</Label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-background border border-border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm min-h-[120px]"
              placeholder="Enter description and tags..."
            />
          </div>
          <div className="space-y-1">
            <Label className="text-sm font-medium">Visibility</Label>
            <Select value={visibility} onValueChange={setVisibility}>
              <SelectTrigger className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pink-500/50 shadow-sm">
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
        <div className="p-4 border-t border-border bg-secondary/30 flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-medium text-sm hover:bg-secondary border border-border"
          >
            Cancel
          </Button>
          <Button
            variant="default"
            onClick={onUpload}
            disabled={isUploading}
            className="px-6 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-medium text-sm shadow-md disabled:opacity-50 flex items-center gap-2"
          >
            {isUploading ? "Starting..." : "Post to TikTok"}
          </Button>
        </div>
      </div>
    </div>
  )
}
