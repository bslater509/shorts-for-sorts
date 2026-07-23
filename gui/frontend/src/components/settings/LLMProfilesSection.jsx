import { Cpu, Plus, Trash, CheckCircle, RefreshCw, Loader2 } from 'lucide-react'

export default function LLMProfilesSection({
  profiles,
  activeProfileId,
  onChange,
  onDelete,
  onSetActive,
  onFetchModels,
  availableModels,
  isFetchingModels,
  onAddProfile,
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Cpu className="text-blue-500" size={20} />
          LLM Profiles
        </h3>
        <button
          onClick={onAddProfile}
          className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Add Profile
        </button>
      </div>

      <div className="space-y-4">
        {(!profiles || profiles.length === 0) ? (
          <p className="text-sm text-muted-foreground italic">No profiles configured. Add one above.</p>
        ) : (
          profiles.map((profile) => (
            <div
              key={profile.id}
              className={`p-4 border rounded-lg space-y-4 ${activeProfileId === profile.id ? 'border-blue-500 bg-blue-500/5' : 'border-border'}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <input
                    type="text"
                    value={profile.name}
                    onChange={(e) => onChange(profile.id, 'name', e.target.value)}
                    className="font-medium bg-transparent border-b border-dashed border-muted-foreground/30 focus:border-blue-500 focus:outline-none"
                    placeholder="Profile Name"
                  />
                  {activeProfileId === profile.id && (
                    <span className="flex items-center gap-1 text-xs font-semibold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded-full">
                      <CheckCircle size={12} /> Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {activeProfileId !== profile.id && (
                    <button
                      onClick={() => onSetActive(profile.id)}
                      className="text-xs px-3 py-1.5 border border-border hover:bg-accent rounded-md"
                    >
                      Set Active
                    </button>
                  )}
                  <button
                    onClick={() => onDelete(profile.id)}
                    className="text-red-500 hover:bg-red-500/10 p-1.5 rounded-md"
                    title="Delete Profile"
                  >
                    <Trash size={16} />
                  </button>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-muted-foreground">API Key (Optional if env set)</label>
                  <input
                    type="password"
                    value={profile.api_key}
                    onChange={(e) => onChange(profile.id, 'api_key', e.target.value)}
                    placeholder="sk-..."
                    className="input-base text-sm py-1.5"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-muted-foreground">API Base URL</label>
                  <input
                    type="text"
                    value={profile.base_url}
                    onChange={(e) => onChange(profile.id, 'base_url', e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    className="input-base text-sm py-1.5"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-muted-foreground flex justify-between items-center">
                    Model Name
                    <button
                      onClick={() => onFetchModels(profile)}
                      disabled={isFetchingModels?.[profile.id]}
                      className="text-blue-500 hover:underline flex items-center gap-1 disabled:opacity-50"
                    >
                      {isFetchingModels?.[profile.id] ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                      Fetch Models
                    </button>
                  </label>
                  {availableModels?.[profile.id] && availableModels[profile.id].length > 0 ? (
                    <select
                      value={profile.model}
                      onChange={(e) => onChange(profile.id, 'model', e.target.value)}
                      className="input-base text-sm py-1.5"
                    >
                      <option value="">-- Select a Model --</option>
                      {availableModels[profile.id].map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={profile.model}
                      onChange={(e) => onChange(profile.id, 'model', e.target.value)}
                      className="input-base text-sm py-1.5"
                      placeholder="e.g. gpt-4o"
                    />
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
