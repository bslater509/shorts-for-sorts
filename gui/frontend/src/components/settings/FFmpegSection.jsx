import { Video } from 'lucide-react'
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

export default function FFmpegSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Video className="text-orange-500" size={20} />
        Render & FFmpeg Configuration
      </h3>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">Vertical Resolution</Label>
          <Select
            value={String(settings.render_resolution)}
            onValueChange={(v) => onChange({ target: { name: 'render_resolution', value: v } })}
          >
            <SelectTrigger className="input-base">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="720p">720p (720x1280)</SelectItem>
              <SelectItem value="1080p">1080p (1080x1920) - Standard</SelectItem>
              <SelectItem value="1440p">1440p (1440x2560)</SelectItem>
              <SelectItem value="4k">4K (2160x3840)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">FFmpeg Preset (Speed vs Size)</Label>
          <Select
            value={String(settings.render_preset)}
            onValueChange={(v) => onChange({ target: { name: 'render_preset', value: v } })}
          >
            <SelectTrigger className="input-base">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ultrafast">ultrafast</SelectItem>
              <SelectItem value="superfast">superfast</SelectItem>
              <SelectItem value="veryfast">veryfast (recommended)</SelectItem>
              <SelectItem value="faster">faster</SelectItem>
              <SelectItem value="fast">fast</SelectItem>
              <SelectItem value="medium">medium</SelectItem>
              <SelectItem value="slow">slow</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">Video Encoder</Label>
          <Select
            value={String(settings.video_encoder)}
            onValueChange={(v) => onChange({ target: { name: 'video_encoder', value: v } })}
          >
            <SelectTrigger className="input-base">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="libx265">libx265 (HEVC CPU - Default)</SelectItem>
              <SelectItem value="libx264">libx264 (CPU)</SelectItem>
              <SelectItem value="h264_nvenc">h264_nvenc (NVIDIA GPU)</SelectItem>
              <SelectItem value="hevc_nvenc">hevc_nvenc (NVIDIA GPU H.265)</SelectItem>
              <SelectItem value="h264_amf">h264_amf (AMD GPU)</SelectItem>
              <SelectItem value="h264_qsv">h264_qsv (Intel QuickSync)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  )
}
