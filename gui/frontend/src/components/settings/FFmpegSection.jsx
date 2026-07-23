import { Video } from 'lucide-react'

export default function FFmpegSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Video className="text-orange-500" size={20} />
        Render & FFmpeg Configuration
      </h3>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Vertical Resolution</label>
          <select
            name="render_resolution"
            value={settings.render_resolution}
            onChange={onChange}
            className="input-base"
          >
            <option value="720p">720p (720x1280)</option>
            <option value="1080p">1080p (1080x1920) - Standard</option>
            <option value="1440p">1440p (1440x2560)</option>
            <option value="4k">4K (2160x3840)</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">FFmpeg Preset (Speed vs Size)</label>
          <select
            name="render_preset"
            value={settings.render_preset}
            onChange={onChange}
            className="input-base"
          >
            <option value="ultrafast">ultrafast</option>
            <option value="superfast">superfast</option>
            <option value="veryfast">veryfast (recommended)</option>
            <option value="faster">faster</option>
            <option value="fast">fast</option>
            <option value="medium">medium</option>
            <option value="slow">slow</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Video Encoder</label>
          <select
            name="video_encoder"
            value={settings.video_encoder}
            onChange={onChange}
            className="input-base"
          >
            <option value="libx265">libx265 (HEVC CPU - Default)</option>
            <option value="libx264">libx264 (CPU)</option>
            <option value="h264_nvenc">h264_nvenc (NVIDIA GPU)</option>
            <option value="hevc_nvenc">hevc_nvenc (NVIDIA GPU H.265)</option>
            <option value="h264_amf">h264_amf (AMD GPU)</option>
            <option value="h264_qsv">h264_qsv (Intel QuickSync)</option>
          </select>
        </div>
      </div>
    </div>
  )
}
