import { Mic } from 'lucide-react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

export default function WhisperSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Mic className="text-purple-500" size={20} />
        Whisper Transcription (Subtitles)
      </h3>
      <div className="grid sm:grid-cols-2 gap-4 mb-4">
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">Transcription Engine</Label>
          <Select
            value={String(settings.local_whisper)}
            onValueChange={(v) => onChange({ target: { name: 'local_whisper', value: v } })}
          >
            <SelectTrigger className="input-base max-w-xs">
              <SelectValue placeholder="Select engine..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">Local CPU/GPU (faster-whisper)</SelectItem>
              <SelectItem value="false">OpenAI API (Cloud)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {settings.local_whisper ? (
        <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">Local Model Size</Label>
            <Select
              value={settings.local_whisper_model}
              onValueChange={(v) => onChange({ target: { name: 'local_whisper_model', value: v } })}
            >
              <SelectTrigger className="input-base">
                <SelectValue placeholder="Select model..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="tiny">tiny (fastest, lowest accuracy)</SelectItem>
                <SelectItem value="base">base</SelectItem>
                <SelectItem value="small">small (recommended)</SelectItem>
                <SelectItem value="medium">medium</SelectItem>
                <SelectItem value="large-v3">large-v3 (slowest, highest accuracy)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">Whisper API Key</Label>
            <Input
              type="password"
              name="whisper_api_key"
              value={settings.whisper_api_key}
              onChange={onChange}
              className="input-base"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label className="text-sm font-medium">Whisper API URL</Label>
            <Input
              type="text"
              name="whisper_base_url"
              value={settings.whisper_base_url}
              onChange={onChange}
              className="input-base"
            />
          </div>
        </div>
      )}
    </div>
  )
}
