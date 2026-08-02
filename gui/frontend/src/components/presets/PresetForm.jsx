import { PaintBucket, Save, Loader2 } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import AnimationSelector from './AnimationSelector'

export default function PresetForm({ form, onChange, animations, voices, onSave, isSaving }) {
  return (
    <div className="flex-1 bg-card border border-border rounded-xl shadow-sm flex flex-col md:overflow-hidden">
      <div className="p-4 border-b border-border bg-secondary/30">
        <h2 className="font-semibold flex items-center gap-2">
          <PaintBucket size={18} className="text-blue-500" />
          Preset Designer
        </h2>
      </div>

      <div className="flex-1 md:overflow-y-auto p-6 overscroll-contain touch-pan-y">
        <form id="preset-form" onSubmit={onSave} className="space-y-8">
          <div className="space-y-4">
            <div className="flex flex-col gap-2">
              <Label className="text-sm font-semibold">Preset Name</Label>
              <Input
                type="text"
                name="name"
                value={form.name}
                onChange={onChange}
                placeholder="e.g. Cinematic Yellow Pop"
                className="input-base text-lg font-medium"
                required
              />
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">
              Subtitle Typography
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Font Family</Label>
                <Select value={form.sub_font} onValueChange={(v) => onChange({ target: { name: 'sub_font', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select font..." />
                  </SelectTrigger>
                  <SelectContent>
                    {['Arial', 'Impact', 'Georgia', 'Times New Roman', 'Courier New', 'Trebuchet MS', 'Verdana', 'Montserrat', 'Roboto', 'Open Sans', 'Inter', 'Bebas Neue', 'Anton', 'Bangers', 'Poppins', 'Raleway'].map((f) => (
                      <SelectItem key={f} value={f}>{f}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Font Size (px)</Label>
                <Input type="number" name="sub_size" value={form.sub_size} onChange={onChange} className="input-base" />
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Font Weight</Label>
                <Select value={form.sub_bold.toString()} onValueChange={(v) => onChange({ target: { name: 'sub_bold', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select weight..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Bold</SelectItem>
                    <SelectItem value="false">Normal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Text Case</Label>
                <Select value={form.sub_uppercase.toString()} onValueChange={(v) => onChange({ target: { name: 'sub_uppercase', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select case..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">ALL CAPS</SelectItem>
                    <SelectItem value="false">Normal Case</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">
              Colors & Styling
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              {[
                { label: 'Primary Text Color', name: 'sub_color' },
                { label: 'Active Word Highlight', name: 'sub_highlight' },
                { label: 'Outline Color', name: 'sub_outline' },
              ].map((colorField) => (
                <div key={colorField.name} className="flex flex-col gap-2">
                  <Label className="text-sm font-medium">{colorField.label}</Label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      name={colorField.name}
                      value={form[colorField.name]}
                      onChange={onChange}
                      className="w-10 h-10 rounded cursor-pointer bg-transparent border-0 p-0"
                    />
                    <Input
                      type="text"
                      name={colorField.name}
                      value={form[colorField.name]}
                      onChange={onChange}
                      className="input-base flex-1 uppercase font-mono"
                    />
                  </div>
                </div>
              ))}
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Outline Border Width</Label>
                <Input
                  type="number"
                  name="sub_outline_width"
                  value={form.sub_outline_width}
                  onChange={onChange}
                  className="input-base"
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">
              Animation & Emojis
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Animation Scheme</Label>
                <AnimationSelector
                  value={form.sub_animation_style}
                  onChange={(val) => onChange({ target: { name: 'sub_animation_style', value: val } })}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Dynamic Emojis Position</Label>
                <Select value={form.emoji_position} onValueChange={(v) => onChange({ target: { name: 'emoji_position', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select position..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="above">Above Text Line</SelectItem>
                    <SelectItem value="same_line">Next to Word</SelectItem>
                    <SelectItem value="none">Disabled (No emojis)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Emoji Animation</Label>
                <Select value={form.enable_emoji_animation.toString()} onValueChange={(v) => onChange({ target: { name: 'enable_emoji_animation', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Enabled (pop/bounce/float/fade/shake)</SelectItem>
                    <SelectItem value="false">Disabled (static emojis)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Emoji Size Scale</Label>
                <Input
                  type="number"
                  name="emoji_scale_factor"
                  value={form.emoji_scale_factor}
                  onChange={onChange}
                  step="0.1"
                  min="0.5"
                  max="3.0"
                  className="input-base"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Emoji Hold (seconds)</Label>
                <Input
                  type="number"
                  name="emoji_hold_duration"
                  value={form.emoji_hold_duration}
                  onChange={onChange}
                  step="0.1"
                  min="0"
                  max="2.0"
                  className="input-base"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Emoji Style</Label>
                <Select value={form.emoji_style} onValueChange={(v) => onChange({ target: { name: 'emoji_style', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select style..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Noto Color Emoji">Noto Color Emoji</SelectItem>
                    <SelectItem value="Symbola">Symbola (Monochrome)</SelectItem>
                    <SelectItem value="Noto Emoji">Noto Emoji (Monochrome)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Word Scale Pop-up</Label>
                <Select value={form.word_pop.toString()} onValueChange={(v) => onChange({ target: { name: 'word_pop', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Enabled (1.15x scale)</SelectItem>
                    <SelectItem value="false">Disabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Dim Inactive Words</Label>
                <Select value={form.inactive_dim.toString()} onValueChange={(v) => onChange({ target: { name: 'inactive_dim', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Dim (opacity: 50%)</SelectItem>
                    <SelectItem value="false">No dimming</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">
              Default Media
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Default Speaker Voice</Label>
                <Select value={form.selected_voice} onValueChange={(v) => onChange({ target: { name: 'selected_voice', value: v } })}>
                  <SelectTrigger className="input-base">
                    <SelectValue placeholder="Select voice..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">(None)</SelectItem>
                    {voices.map((v) => (
                      <SelectItem key={v.value} value={v.value}>{v.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Voice Speed Factor</Label>
                <Input
                  type="number"
                  step="0.05"
                  name="voice_speed"
                  value={form.voice_speed}
                  onChange={onChange}
                  className="input-base"
                />
              </div>
            </div>
          </div>
        </form>
      </div>

      <div className="p-4 border-t border-border bg-secondary/30">
        <Button
          type="submit"
          form="preset-form"
          disabled={isSaving}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium shadow-md shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          Save Preset Template
        </Button>
      </div>
    </div>
  )
}
