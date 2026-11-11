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

function WishPhoto({ wish }: { wish: Wish }) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    if (!wish.has_photo) return
    let url: string | null = null
    let cancelled = false
    api
      .wishPhoto(wish.id)
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
  }, [wish.id, wish.has_photo])

  return src ? (
    <img className="wish-photo" src={src} alt="" />
  ) : (
    <div className="wish-photo wish-photo-placeholder" aria-hidden>
      🎁
    </div>
  )
}

export default function WishCard({ wish }: { wish: Wish }) {
  const [expanded, setExpanded] = useState(false)
  const priority = PRIORITIES.find((p) => p.value === wish.priority)

  return (
    <article className="wish-card">
      <WishPhoto wish={wish} />
      <div className="wish-body">
        <h3 className="wish-title">{wish.title}</h3>
        <div className="wish-meta">
          {priority && (
            <span className={`priority-badge priority-${wish.priority}`}>{priority.label}</span>
          )}
          {wish.price !== null && <span className="wish-price">{formatPrice(wish.price)}</span>}
        </div>
        {wish.description && (
          <p
            className={`wish-description ${expanded ? 'expanded' : ''}`}
            role="button"
            tabIndex={0}
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                setExpanded((v) => !v)
              }
            }}
          >
            {wish.description}
          </p>
        )}
        {wish.url && (
          <button type="button" className="link" onClick={() => openLink(wish.url!)}>
            🔗 Відкрити посилання
          </button>
        )}
      </div>
    </article>
  )
}
