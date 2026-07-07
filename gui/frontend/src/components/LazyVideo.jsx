import useInView from '@/hooks/useInView'

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
          <img
            src={poster}
            alt=""
            className="absolute inset-0 w-full h-full object-cover opacity-60"
            loading="lazy"
          />
        ) : (
          <div className="absolute inset-0 bg-secondary/30" />
        )
      )}
    </div>
  )
}
