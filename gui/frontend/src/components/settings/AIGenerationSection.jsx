import { FileText } from 'lucide-react'

export default function AIGenerationSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <FileText className="text-violet-500" size={20} />
        AI Script Generation
      </h3>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium">System Prompt</label>
        <textarea
          name="system_prompt"
          value={settings.system_prompt || ''}
          onChange={onChange}
          rows={24}
          className="input-base text-sm py-1.5 font-mono resize-y min-h-[300px]"
          placeholder="Default: You are an elite TikTok and YouTube Shorts scriptwriter..."
        />
        <p className="text-xs text-muted-foreground">
          The system prompt sent to the LLM for every script generation. Leave empty to use the built-in default.
        </p>
      </div>

      <div className="grid sm:grid-cols-3 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Script Temperature</label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            name="llm_temp_script"
            value={settings.llm_temp_script ?? 0.7}
            onChange={onChange}
            className="input-base"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Metadata Temperature</label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            name="llm_temp_metadata"
            value={settings.llm_temp_metadata ?? 0.7}
            onChange={onChange}
            className="input-base"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Keywords Temperature</label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            name="llm_temp_keywords"
            value={settings.llm_temp_keywords ?? 0.7}
            onChange={onChange}
            className="input-base"
          />
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Max Script Words</label>
          <input
            type="number"
            min="50"
            max="2000"
            step="50"
            name="max_words"
            value={settings.max_words || ''}
            onChange={onChange}
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Target word count for generated scripts.</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Default Batch Size</label>
          <input
            type="number"
            min="1"
            max="100"
            name="default_batch_size"
            value={settings.default_batch_size || ''}
            onChange={onChange}
            className="input-base"
          />
          <p className="text-xs text-muted-foreground">Default number of shorts in a batch.</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Words Per Screen</label>
          <select
            name="words_per_screen"
            value={settings.words_per_screen || '3'}
            onChange={onChange}
            className="input-base"
          >
            <option value="1">1 word</option>
            <option value="3">3 words</option>
            <option value="sentence">Full sentence</option>
            <option value="random">Random</option>
          </select>
          <p className="text-xs text-muted-foreground">How many words appear per subtitle screen.</p>
        </div>
      </div>
    </div>
  )
}
