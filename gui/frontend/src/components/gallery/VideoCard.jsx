import { Hash, Share2, Download, Trash2 } from 'lucide-react'
import LazyVideo from '@/components/LazyVideo'
import TikTokIcon from './TikTokIcon'

const formatSize = (bytes) => {
  if (!bytes) return '0 MB'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (timestamp) => {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString()
}

export default function VideoCard({ video, onCopyHashtags, onShare, onTikTokUpload, onDelete }) {
  return (
    <div className="group bg-card border border-border rounded-xl overflow-hidden shadow-sm hover:border-blue-500/30 transition-colors flex flex-col" style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 500px' }}>
      <div className="relative aspect-[9/16] bg-black">
        <LazyVideo
          src={video.url}
          poster={video.thumbnail}
        />
      </div>

      <div className="p-4 flex flex-col gap-3 flex-1 bg-secondary/10">
        <div>
          <h3 className="font-semibold text-sm leading-tight truncate" title={video.filename}>
            {video.filename}
          </h3>
          <div className="flex items-center justify-between mt-1 text-xs text-muted-foreground">
            <span>{video.duration ? `${video.duration.toFixed(1)}s` : 'Short'} • {formatSize(video.size)}</span>
            <span>{formatDate(video.modified)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-auto pt-2">
          {video.hashtags && (
            <button
              onClick={() => onCopyHashtags(video)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-purple-500 hover:bg-purple-600 text-white rounded-md text-xs font-semibold transition-colors"
              title="Copy Hashtags"
            >
              <Hash size={14} />
            </button>
          )}
          <button
            onClick={() => onShare(video)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-md text-xs font-semibold transition-colors"
            title="Share Video"
          >
            <Share2 size={14} />
          </button>
          <button
            onClick={() => onTikTokUpload(video)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white rounded-md text-xs font-semibold transition-colors"
            title="Upload to TikTok"
          >
            <TikTokIcon size={14} />
          </button>
          <a
            href={video.url}
            download={video.filename}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white rounded-md text-xs font-semibold transition-colors"
            title="Download Video"
          >
            <Download size={14} />
          </a>
          <button
            onClick={() => onDelete(video.filename)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white rounded-md text-xs font-semibold transition-colors"
            title="Delete Video"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
