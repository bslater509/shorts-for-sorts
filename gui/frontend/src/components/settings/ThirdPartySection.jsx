import { Key } from 'lucide-react'

export default function ThirdPartySection({ settings, onChange, onTikTokLogin }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Key className="text-emerald-500" size={20} />
        Third Party APIs & Integrations
      </h3>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Pexels API Key (For Auto-B-Roll)</label>
          <input
            type="password"
            name="pexels_api_key"
            value={settings.pexels_api_key}
            onChange={onChange}
            placeholder="Optional"
            className="input-base"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Sentry DSN (Error Tracking)</label>
          <input
            type="text"
            name="sentry_dsn"
            value={settings.sentry_dsn || ''}
            onChange={onChange}
            placeholder="https://..."
            className="input-base"
          />
        </div>
        <div className="flex flex-col gap-2 md:col-span-2">
          <label className="text-sm font-medium">TikTok Session ID (For Auto-Uploading)</label>
          <div className="flex gap-2">
            <input
              type="password"
              name="tiktok_sessionid"
              value={settings.tiktok_sessionid || ''}
              onChange={onChange}
              placeholder="Paste sessionid cookie or login..."
              className="input-base flex-1"
            />
            <button
              onClick={onTikTokLogin}
              className="px-4 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg font-medium text-sm transition-colors whitespace-nowrap"
            >
              Login to TikTok
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
