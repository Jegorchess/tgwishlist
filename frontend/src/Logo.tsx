/** «Хотєлочки» logo: a shooting star — "make a wish". Colours follow the Telegram theme. */
export function StarIcon({ size = 34 }: { size?: number }) {
  return (
    <svg
      className="logo-star"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
    >
      {/* the trail */}
      <path d="M4 40 L19 27" className="logo-trail" />
      <path d="M8 46 L21 33" className="logo-trail logo-trail-soft" />
      <path d="M2 31 L15 22" className="logo-trail logo-trail-soft" />
      {/* the star */}
      <path
        className="logo-star-body"
        d="M31 4.5l4.1 8.6 9.4 1.2-6.9 6.5 1.8 9.3L31 25.6l-8.4 4.5 1.8-9.3-6.9-6.5 9.4-1.2z"
      />
    </svg>
  )
}

export default function Logo() {
  return (
    <h1 className="logo">
      <StarIcon />
      <span className="logo-text">Хотєлочки</span>
    </h1>
  )
}
