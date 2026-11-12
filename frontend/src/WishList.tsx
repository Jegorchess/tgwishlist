import { useState } from 'react'
import type { Wish } from './api'
import { filterWishes, SEARCH_THRESHOLD, SearchBox } from './search'
import WishCard from './WishCard'

interface Props {
  wishes: Wish[] | null
  error: boolean
  onRetry: () => void
  onAdd: () => void
  onOpen: (wish: Wish) => void
  /** Received wishes; the block is hidden when empty. */
  archived: Wish[]
}

export default function WishList({ wishes, error, onRetry, onAdd, onOpen, archived }: Props) {
  const [query, setQuery] = useState('')

  if (error) {
    return (
      <section className="wish-list-state">
        <p className="error">Не вдалося завантажити список хотєлок.</p>
        <button type="button" className="secondary" onClick={onRetry}>
          Спробувати ще раз
        </button>
      </section>
    )
  }

  if (wishes === null) {
    return (
      <section className="wish-list-state">
        <div className="spinner" role="status" aria-label="Завантаження" />
      </section>
    )
  }

  if (wishes.length === 0) {
    return (
      <>
        <section className="wish-list-state">
          <p className="hint">Тут поки порожньо — додай першу хотєлку</p>
          <button type="button" className="primary" onClick={onAdd}>
            ➕ Додати хотєлку
          </button>
        </section>
        <Archive wishes={archived} onOpen={onOpen} />
      </>
    )
  }

  return (
    <section>
      <button type="button" className="primary" onClick={onAdd}>
        ➕ Додати хотєлку
      </button>
      <h2 className="section-title">Мої хотєлки</h2>
      <p className="hint small">Натисни на хотєлку, щоб змінити або видалити її</p>
      {wishes.length > SEARCH_THRESHOLD && <SearchBox value={query} onChange={setQuery} />}
      <FilteredWishes wishes={wishes} query={query} onOpen={onOpen} />
      <Archive wishes={archived} onOpen={onOpen} />
    </section>
  )
}

function FilteredWishes({
  wishes,
  query,
  onOpen,
}: {
  wishes: Wish[]
  query: string
  onOpen: (wish: Wish) => void
}) {
  const shown = filterWishes(wishes, query)
  if (shown.length === 0)
    return (
      <p className="hint wish-list-state" role="status">
        Нічого не знайдено
      </p>
    )
  return (
    <div className="wish-list">
      {shown.map((w) => (
        <WishCard key={w.id} wish={w} onOpen={onOpen} />
      ))}
    </div>
  )
}

/** «Архів»: received wishes, collapsed by default. Tap opens one to restore or delete it. */
function Archive({ wishes, onOpen }: { wishes: Wish[]; onOpen: (wish: Wish) => void }) {
  if (wishes.length === 0) return null
  return (
    <details className="archive">
      <summary>🎉 Архів ({wishes.length})</summary>
      <div className="wish-list archive-list">
        {wishes.map((w) => (
          <WishCard key={w.id} wish={w} onOpen={onOpen} />
        ))}
      </div>
    </details>
  )
}
