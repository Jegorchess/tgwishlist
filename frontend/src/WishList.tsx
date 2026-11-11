import type { Wish } from './api'
import WishCard from './WishCard'

interface Props {
  wishes: Wish[] | null
  error: boolean
  onRetry: () => void
  onAdd: () => void
}

export default function WishList({ wishes, error, onRetry, onAdd }: Props) {
  if (error) {
    return (
      <section className="wish-list-state">
        <p className="error">Не вдалося завантажити список бажань.</p>
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
      <section className="wish-list-state">
        <p className="hint">Тут поки порожньо — додай перше бажання</p>
        <button type="button" className="primary" onClick={onAdd}>
          ➕ Додати бажання
        </button>
      </section>
    )
  }

  return (
    <section>
      <button type="button" className="primary" onClick={onAdd}>
        ➕ Додати бажання
      </button>
      <h2 className="section-title">Мої бажання</h2>
      <div className="wish-list">
        {wishes.map((w) => (
          <WishCard key={w.id} wish={w} />
        ))}
      </div>
    </section>
  )
}
