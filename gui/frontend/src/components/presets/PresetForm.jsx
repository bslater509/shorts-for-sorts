import { PaintBucket, Save, Loader2 } from 'lucide-react'
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

      <div className="flex-1 md:overflow-y-auto p-6">
        <form id="preset-form" onSubmit={onSave} className="space-y-8">
          <div className="space-y-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold">Preset Name</label>
              <input
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
                <label className="text-sm font-medium">Font Family</label>
                <select name="sub_font" value={form.sub_font} onChange={onChange} className="input-base">
                  {['Arial', 'Impact', 'Georgia', 'Times New Roman', 'Courier New', 'Trebuchet MS', 'Verdana', 'Montserrat', 'Roboto', 'Open Sans', 'Inter', 'Bebas Neue', 'Anton', 'Bangers', 'Poppins', 'Raleway'].map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Font Size (px)</label>
                <input type="number" name="sub_size" value={form.sub_size} onChange={onChange} className="input-base" />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Font Weight</label>
                <select name="sub_bold" value={form.sub_bold.toString()} onChange={onChange} className="input-base">
                  <option value="true">Bold</option>
                  <option value="false">Normal</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Text Case</label>
                <select name="sub_uppercase" value={form.sub_uppercase.toString()} onChange={onChange} className="input-base">
                  <option value="true">ALL CAPS</option>
                  <option value="false">Normal Case</option>
                </select>
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
                  <label className="text-sm font-medium">{colorField.label}</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      name={colorField.name}
                      value={form[colorField.name]}
                      onChange={onChange}
                      className="w-10 h-10 rounded cursor-pointer bg-transparent border-0 p-0"
                    />
                    <input
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
                <label className="text-sm font-medium">Outline Border Width</label>
                <input
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
                <label className="text-sm font-medium">Animation Scheme</label>
                <AnimationSelector
                  value={form.sub_animation_style}
                  onChange={(val) => onChange({ target: { name: 'sub_animation_style', value: val } })}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Dynamic Emojis Position</label>
                <select
                  name="emoji_position"
                  value={form.emoji_position}
                  onChange={onChange}
                  className="input-base"
                >
                  <option value="above">Above Text Line</option>
                  <option value="same_line">Next to Word</option>
                  <option value="none">Disabled (No emojis)</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Emoji Animation</label>
                <select
                  name="enable_emoji_animation"
                  value={form.enable_emoji_animation.toString()}
                  onChange={onChange}
                  className="input-base"
                >
                  <option value="true">Enabled (pop/bounce/float/fade/shake)</option>
                  <option value="false">Disabled (static emojis)</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Emoji Size Scale</label>
                <input
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
                <label className="text-sm font-medium">Emoji Hold (seconds)</label>
                <input
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
                <label className="text-sm font-medium">Emoji Style</label>
                <select name="emoji_style" value={form.emoji_style} onChange={onChange} className="input-base">
                  <option value="apple">Apple</option>
                  <option value="twemoji">Twemoji (Twitter)</option>
                  <option value="google">Google</option>
                  <option value="facebook">Facebook</option>
                  <option value="openmoji">OpenMoji</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Word Scale Pop-up</label>
                <select
                  name="word_pop"
                  value={form.word_pop.toString()}
                  onChange={onChange}
                  className="input-base"
                >
                  <option value="true">Enabled (1.15x scale)</option>
                  <option value="false">Disabled</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Dim Inactive Words</label>
                <select
                  name="inactive_dim"
                  value={form.inactive_dim.toString()}
                  onChange={onChange}
                  className="input-base"
                >
                  <option value="true">Dim (opacity: 50%)</option>
                  <option value="false">No dimming</option>
                </select>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2">
              Default Media
            </h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Default Speaker Voice</label>
                <select
                  name="selected_voice"
                  value={form.selected_voice}
                  onChange={onChange}
                  className="input-base"
                >
                  <option value="">(None)</option>
                  {voices.map((v) => (
                    <option key={v.value} value={v.value}>{v.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Voice Speed Factor</label>
                <input
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
        <button
          type="submit"
          form="preset-form"
          disabled={isSaving}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium shadow-md shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          Save Preset Template
        </button>
      </div>
    </div>
  )
}
