import { useState } from 'react'
import LazyVideo from '@/components/LazyVideo'

export default function InlineVideoPreview({ videoUrl, thumbnail, className = '' }) {
  const [showControls, setShowControls] = useState(false)

  if (!videoUrl) return null

  return (
    <div
      className={`relative aspect-[9/16] rounded-lg overflow-hidden border border-border/50 bg-black cursor-pointer group ${className}`}
      onClick={(e) => {
        e.stopPropagation()
        setShowControls(true)
        const video = e.currentTarget.querySelector('video')
        if (video && video.paused) video.play().catch(() => {})
      }}
    >
      {showControls ? (
        <LazyVideo src={videoUrl} poster={thumbnail} />
      ) : (
        <>
          {thumbnail ? (
            <img src={thumbnail} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
          ) : (
            <div className="absolute inset-0 bg-secondary/30" />
          )}
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
            <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center group-hover:scale-110 transition-transform">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                <polygon points="5,3 19,12 5,21" />
              </svg>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
