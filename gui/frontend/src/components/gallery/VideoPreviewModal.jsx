import { useEffect } from 'react'
import { X } from 'lucide-react'
import InlineVideoPreview from '@/components/batch/InlineVideoPreview'

export default function VideoPreviewModal({ video, onClose }) {
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="flex flex-col w-full max-w-sm animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3 gap-3">
          <h2 className="text-sm font-semibold text-white/90 truncate" title={video.filename}>
            {video.filename}
          </h2>
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white/70 hover:text-white transition-colors"
            aria-label="Close preview"
          >
            <X size={16} />
          </button>
        </div>

        {/* Video */}
        <InlineVideoPreview
          videoUrl={video.url}
          thumbnail={video.thumbnail}
          className="w-full"
        />
      </div>
    </div>
  )
}
