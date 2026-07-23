import { Edit2, Trash2 } from 'lucide-react'

export default function PresetListItem({ preset, name, onEdit, onDelete }) {
  return (
    <div className="bg-secondary/50 border border-border rounded-lg p-3 hover:border-blue-500/30 transition-colors">
      <h4 className="font-semibold text-sm truncate" title={name}>
        {name}
      </h4>
      <p className="text-xs text-muted-foreground mt-1 truncate">
        {preset.sub_animation_style} &bull; {preset.sub_font}
      </p>
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
        <button
          onClick={() => onEdit(name)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1 bg-background hover:bg-blue-500 hover:text-white border border-border hover:border-blue-500 rounded text-xs font-medium transition-colors"
        >
          <Edit2 size={12} /> Edit
        </button>
        <button
          onClick={() => onDelete(name)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1 bg-background hover:bg-red-500 hover:text-white border border-border hover:border-red-500 rounded text-xs font-medium transition-colors"
        >
          <Trash2 size={12} /> Delete
        </button>
      </div>
    </div>
  )
}
