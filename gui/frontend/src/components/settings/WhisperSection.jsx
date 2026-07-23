import { Mic } from 'lucide-react'

export default function WhisperSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Mic className="text-purple-500" size={20} />
        Whisper Transcription (Subtitles)
      </h3>
      <div className="grid sm:grid-cols-2 gap-4 mb-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Transcription Engine</label>
          <select
            name="local_whisper"
            value={String(settings.local_whisper)}
            onChange={onChange}
            className="input-base max-w-xs"
          >
            <option value="true">Local CPU/GPU (faster-whisper)</option>
            <option value="false">OpenAI API (Cloud)</option>
          </select>
        </div>
      </div>

      {settings.local_whisper ? (
        <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">Local Model Size</label>
            <select
              name="local_whisper_model"
              value={settings.local_whisper_model}
              onChange={onChange}
              className="input-base"
            >
              <option value="tiny">tiny (fastest, lowest accuracy)</option>
              <option value="base">base</option>
              <option value="small">small (recommended)</option>
              <option value="medium">medium</option>
              <option value="large-v3">large-v3 (slowest, highest accuracy)</option>
            </select>
          </div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4 animate-in fade-in duration-300">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">Whisper API Key</label>
            <input
              type="password"
              name="whisper_api_key"
              value={settings.whisper_api_key}
              onChange={onChange}
              className="input-base"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">Whisper API URL</label>
            <input
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
