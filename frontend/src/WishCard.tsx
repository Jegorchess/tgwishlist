import { useEffect, useState, type ReactNode } from 'react'
import { api, type Wish } from './api'
import { openLink } from './telegram'
import { PRIORITIES } from './wishForm'

const priceFormat = new Intl.NumberFormat('uk-UA', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** "4250.00" -> "4 250,00 zł" */
export function formatPrice(price: string): string {
  return `${priceFormat.format(Number(price))} zł`
}

/** Object URL of the wish's photo (fetched with auth); null while loading or without a photo. */
export function useWishPhoto(wish: Wish | undefined): string | null {
  const [src, setSrc] = useState<string | null>(null)
  const id = wish?.id
  const version = wish?.photo_version ?? null

  useEffect(() => {
    setSrc(null)
    if (id === undefined || version === null) return
    let url: string | null = null
    let cancelled = false
    api
      .wishPhoto(id, version)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => setSrc(null)) // fall back to the placeholder
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [id, version])

  return src
}

function WishPhoto({ wish }: { wish: Wish }) {
  const src = useWishPhoto(wish)
  return src ? (
    <img className="wish-photo" src={src} alt="" />
  ) : (
    <div className="wish-photo wish-photo-placeholder" aria-hidden>
      <GiftIcon />
    </div>
  )
}

/** Line-art gift for wishes without a photo; drawn in the theme accent color. */
function GiftIcon() {
  return (
    <svg viewBox="0 0 24 24" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3.5" y="8" width="17" height="4" rx="1" />
        <path d="M5 12v7.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V12M12 8v12.5" />
        <path d="M12 8c-1-2.6-4.5-3.6-4.5-1.3C7.5 8 10 8 12 8Zm0 0c1-2.6 4.5-3.6 4.5-1.3C16.5 8 14 8 12 8Z" />
      </g>
    </svg>
  )
}

interface Props {
  wish: Wish
  /** Tap on the card opens editing; omit for read-only cards (someone else's wish). */
  onOpen?: (wish: Wish) => void
  /** Extra controls at the bottom of the card (e.g. «Я дарую»). */
  footer?: ReactNode
  /** Shows the standard share icon in the corner (my own active wishes). */
  onShare?: (wish: Wish) => void
}

/** The usual "share" glyph: a box with an arrow going up. */
function ShareIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path
        d="M12 3v12M7.5 7.5 12 3l4.5 4.5M8 11H6a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function WishCard({ wish, onOpen, footer, onShare }: Props) {
  const [expanded, setExpanded] = useState(false)
  const priority = PRIORITIES.find((p) => p.value === wish.priority)

  return (
    // The title button is stretched over the whole card (CSS ::after), so tapping anywhere
    // opens editing; the description toggle and the link sit above it as separate controls.
    <article
      className={['wish-card', onOpen && 'clickable', onShare && 'shareable']
        .filter(Boolean)
        .join(' ')}
    >
      {onShare && (
        <button
          type="button"
          className="share-icon above-card-link"
          aria-label={`Поділитися «${wish.title}»`}
          title="Поділитися"
          onClick={() => onShare(wish)}
        >
          <ShareIcon />
        </button>
      )}
      <WishPhoto wish={wish} />
      <div className="wish-body">
        <h3 className="wish-title">
          {onOpen ? (
            <button
              type="button"
              className="wish-open"
              aria-label={`Редагувати «${wish.title}»`}
              onClick={() => onOpen(wish)}
            >
              {wish.title}
            </button>
          ) : (
            wish.title
          )}
        </h3>
        {wish.price !== null && <span className="wish-price">{formatPrice(wish.price)}</span>}
        {priority && (
          <span className={`priority-badge priority-${wish.priority}`}>{priority.label}</span>
        )}
        {wish.description && (
          <button
            type="button"
            className={`wish-description above-card-link ${expanded ? 'expanded' : ''}`}
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {wish.description}
          </button>
        )}
        {wish.url && (
          <button
            type="button"
            className="link above-card-link"
            onClick={() => openLink(wish.url!)}
          >
            🔗 Відкрити посилання
          </button>
        )}
        {footer && <div className="above-card-link card-footer">{footer}</div>}
      </div>
    </article>
  )
}
