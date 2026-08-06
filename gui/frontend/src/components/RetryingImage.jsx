import { useState, useRef, useEffect } from 'react'

/**
 * Displays an image with automatic retry-on-404.
 *
 * Background-generated thumbnails may 404 on first request while a worker
 * builds them. This component retries the failed request with exponential
 * backoff (1.5s, 3s, 6s, 12s, 24s, 30s — capped at 30s) and appends a
 * cache-busting `&retry={n}` param on each attempt so the browser re-fetches.
 *
 * Props:
 *   src        — image URL (may already contain query params; preserved)
 *   alt        — alt text
 *   className  — passed through to both the <img> and the fallback placeholder
 *   maxRetries — how many retry attempts before giving up (default 6)
 *   ...rest    — any other <img> attributes
 */
export default function RetryingImage({ src, alt = '', className = '', maxRetries = 6, ...rest }) {
  const [retry, setRetry] = useState(0)
  const [failed, setFailed] = useState(false)
  const timerRef = useRef(null)

  // If the caller swaps the src (e.g. new video selected), start fresh.
  useEffect(() => {
    setRetry(0)
    setFailed(false)
  }, [src])

  // Clear any pending retry timer on unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleError = () => {
    if (timerRef.current) return // already retrying
    if (retry >= maxRetries) {
      setFailed(true)
      return
    }
    const delay = Math.min(1500 * Math.pow(2, retry), 30000)
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      setRetry(r => r + 1)
    }, delay)
  }

  // No src at all (or retries exhausted) — show the subtle placeholder.
  if (failed || !src) {
    return <div className={`bg-secondary/30 ${className}`} {...rest} />
  }

  const bustedSrc = retry > 0
    ? `${src}${src.includes('?') ? '&' : '?'}retry=${retry}`
    : src

  return (
    <img
      src={bustedSrc}
      alt={alt}
      loading="lazy"
      className={className}
      onError={handleError}
      {...rest}
    />
  )
}
