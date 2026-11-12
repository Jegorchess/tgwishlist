import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type OthersWish, type Person, type Reservation } from './api'
import Avatar from './Avatar'
import { fullName, wishCountLabel } from './PeopleList'
import { filterWishes, SEARCH_THRESHOLD, SearchBox } from './search'
import { insideTelegram, useBackButton } from './telegram'
import ReservationControl from './ReservationControl'
import WishCard from './WishCard'

interface Props {
  person: Person
  onBack: () => void
}

/** Someone else's wishes: read-only. */
export default function PersonWishes({ person, onBack }: Props) {
  const [wishes, setWishes] = useState<OthersWish[] | null>(null)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')

  useBackButton(onBack)

  const latest = useRef(0)

  const load = useCallback(() => {
    const request = ++latest.current
    setError(false)
    setWishes(null)
    api
      .personWishes(person.id)
      .then((list) => request === latest.current && setWishes(list))
      .catch(() => request === latest.current && setError(true))
  }, [person.id])

  const setReservation = useCallback((wishId: number, reservation: Reservation | null) => {
    setWishes((list) => list && list.map((w) => (w.id === wishId ? { ...w, reservation } : w)))
  }, [])

  // After a conflict, show the real state without the loading spinner.
  const refresh = useCallback(() => {
    const request = ++latest.current
    api
      .personWishes(person.id)
      .then((list) => request === latest.current && setWishes(list))
      .catch(() => {})
  }, [person.id])

  useEffect(() => {
    const counter = latest // a plain counter, not a DOM node
    load()
    return () => {
      counter.current++ // unmounted: ignore whatever is still in flight
    }
  }, [load])

  const shown = wishes ? filterWishes(wishes, query) : []

  return (
    <section>
      <header className="person-header">
        <Avatar name={person.first_name} photoUrl={person.photo_url} size={88} />
        <h2 className="person-title">{fullName(person)}</h2>
        <p className="hint">{wishCountLabel(wishes?.length ?? person.wish_count)}</p>
      </header>

      {error && (
        <div className="wish-list-state">
          <p className="error">Не вдалося завантажити список.</p>
          <button type="button" className="secondary" onClick={load}>
            Спробувати ще раз
          </button>
        </div>
      )}
      {!error && wishes === null && (
        <div className="wish-list-state">
          <div className="spinner" role="status" aria-label="Завантаження" />
        </div>
      )}
      {wishes && wishes.length === 0 && (
        <p className="hint wish-list-state">Поки що тут немає хотєлок</p>
      )}
      {wishes && wishes.length > SEARCH_THRESHOLD && (
        <SearchBox value={query} onChange={setQuery} />
      )}
      {wishes && wishes.length > 0 && shown.length === 0 && (
        <p className="hint wish-list-state" role="status">
          Нічого не знайдено
        </p>
      )}
      {shown.length > 0 && (
        <div className="wish-list person-wishes">
          {shown.map((w) => (
            <WishCard
              key={w.id}
              wish={w}
              footer={
                <ReservationControl
                  wish={w}
                  onChange={(r) => setReservation(w.id, r)}
                  onConflict={refresh}
                />
              }
            />
          ))}
        </div>
      )}

      {!insideTelegram && (
        <button type="button" className="secondary back-button" onClick={onBack}>
          ← До списку людей
        </button>
      )}
    </section>
  )
}
