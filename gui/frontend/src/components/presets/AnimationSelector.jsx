export const ANIMATIONS = [
  { value: "tiktok_pop", label: "TikTok Classic (WordPop)" },
  { value: "karaoke_sweep", label: "Karaoke Sweep (Smooth)" },
  { value: "bouncy_bounce", label: "Bouncy Jump (Kinetic)" },
  { value: "cinematic_zoom", label: "Cinematic Zoom (Fade)" },
  { value: "glow_shake", label: "Glow Shake (Tilt)" },
  { value: "neon_flicker", label: "Neon Flicker (Flicker)" },
  { value: "pulse_grow", label: "Pulse Grow (Hype)" },
  { value: "fade_in_slide", label: "Fade-in Slide (Smooth)" },
  { value: "typewriter_swipe", label: "Typewriter Swipe (Reveal)" },
]

export default function AnimationSelector({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="input-base"
    >
      {ANIMATIONS.map((a) => (
        <option key={a.value} value={a.value}>
          {a.label}
        </option>
      ))}
    </select>
  )
}
