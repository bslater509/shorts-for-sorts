import { FileText } from 'lucide-react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

export default function AIGenerationSection({ settings, onChange }) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <FileText className="text-violet-500" size={20} />
        AI Script Generation
      </h3>

      <div className="flex flex-col gap-2">
        <Label className="text-sm font-medium">System Prompt</Label>
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
          <Label className="text-sm font-medium">Script Temperature</Label>
          <Input
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
          <Label className="text-sm font-medium">Metadata Temperature</Label>
          <Input
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
          <Label className="text-sm font-medium">Keywords Temperature</Label>
          <Input
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
          <Label className="text-sm font-medium">Max Script Words</Label>
          <Input
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
          <Label className="text-sm font-medium">Default Batch Size</Label>
          <Input
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
          <Label className="text-sm font-medium">On Batch Failure</Label>
          <Select
            value={String(settings.batch_failure_mode || 'stop_all')}
            onValueChange={(v) => onChange({ target: { name: 'batch_failure_mode', value: v } })}
          >
            <SelectTrigger className="input-base">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="stop_all">Stop all jobs</SelectItem>
              <SelectItem value="continue">Continue remaining jobs</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">Stop entire batch on any failure, or continue with remaining jobs.</p>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-sm font-medium">Words Per Screen</Label>
          <Select
            value={String(settings.words_per_screen || '3')}
            onValueChange={(v) => onChange({ target: { name: 'words_per_screen', value: v } })}
          >
            <SelectTrigger className="input-base">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 word</SelectItem>
              <SelectItem value="3">3 words</SelectItem>
              <SelectItem value="sentence">Full sentence</SelectItem>
              <SelectItem value="random">Random</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">How many words appear per subtitle screen.</p>
        </div>
      </div>
    </div>
  )
}
