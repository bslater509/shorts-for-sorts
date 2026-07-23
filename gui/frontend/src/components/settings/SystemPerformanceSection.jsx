import { Activity } from 'lucide-react'

export default function SystemPerformanceSection({ settings, onChange, notificationStatus, onRequestNotification }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Activity className="text-blue-400" size={20} />
        System & Performance
      </h3>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Max Parallel Operations (CPU/Rendering)</label>
          <input
            type="number"
            min="1"
            max="64"
            name="max_workers"
            value={settings.max_workers || ''}
            onChange={onChange}
            placeholder="Default: CPU Count"
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Controls how many videos render/process at once.</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Max Parallel LLM API Requests</label>
          <input
            type="number"
            min="1"
            max="64"
            name="llm_max_workers"
            value={settings.llm_max_workers || ''}
            onChange={onChange}
            placeholder="Default: 5"
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Controls how many LLM scripts generate concurrently.</p>
        </div>
      </div>

      <div className="pt-4 border-t border-border mt-4">
        <h4 className="text-sm font-medium mb-2">Web Notifications</h4>
        <div className="flex items-center gap-4">
          <p className="text-xs text-muted-foreground flex-1">
            Enable background notifications for job completions. (On iOS, add this page to your Home Screen first).
            <br />
            Status: <strong>{notificationStatus}</strong>
          </p>
          {notificationStatus !== 'granted' && notificationStatus !== 'unsupported' && (
            <button
              onClick={onRequestNotification}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium text-sm transition-colors whitespace-nowrap shadow-sm"
            >
              Enable Notifications
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
