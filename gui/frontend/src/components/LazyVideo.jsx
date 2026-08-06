import useInView from '@/hooks/useInView'
import RetryingImage from '@/components/RetryingImage'

export default function LazyVideo({ src, poster, ...props }) {
  const [ref, isInView] = useInView()

  return (
    <div ref={ref} className="absolute inset-0 bg-black">
      {isInView ? (
        <video
          className="absolute inset-0 w-full h-full object-contain"
          src={src}
          poster={poster}
          preload="metadata"
          controls
          playsInline
          {...props}
        />
      ) : (
        poster ? (
          <RetryingImage
            src={poster}
            alt=""
            className="absolute inset-0 w-full h-full object-cover opacity-60"
          />
        ) : (
          <div className="absolute inset-0 bg-secondary/30" />
        )
      )}
    </div>
  )
}
