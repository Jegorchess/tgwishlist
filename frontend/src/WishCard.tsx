import { useEffect, useState } from 'react'
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
      🎁
    </div>
  )
}

interface Props {
  wish: Wish
  /** Tap on the card opens editing. */
  onOpen: (wish: Wish) => void
}

export default function WishCard({ wish, onOpen }: Props) {
  const [expanded, setExpanded] = useState(false)
  const priority = PRIORITIES.find((p) => p.value === wish.priority)

  return (
    // The title button is stretched over the whole card (CSS ::after), so tapping anywhere
    // opens editing; the description toggle and the link sit above it as separate controls.
    <article className="wish-card">
      <WishPhoto wish={wish} />
      <div className="wish-body">
        <h3 className="wish-title">
          <button
            type="button"
            className="wish-open"
            aria-label={`Редагувати «${wish.title}»`}
            onClick={() => onOpen(wish)}
          >
            {wish.title}
          </button>
        </h3>
        <div className="wish-meta">
          {priority && (
            <span className={`priority-badge priority-${wish.priority}`}>{priority.label}</span>
          )}
          {wish.price !== null && <span className="wish-price">{formatPrice(wish.price)}</span>}
        </div>
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
      </div>
    </article>
  )
}
