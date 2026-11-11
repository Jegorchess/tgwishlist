import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Person, type Wish } from './api'
import Avatar from './Avatar'
import { fullName } from './PeopleList'
import { insideTelegram, useBackButton } from './telegram'
import WishCard from './WishCard'

interface Props {
  person: Person
  onBack: () => void
}

/** Someone else's wishes: read-only. */
export default function PersonWishes({ person, onBack }: Props) {
  const [wishes, setWishes] = useState<Wish[] | null>(null)
  const [error, setError] = useState(false)

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

  useEffect(() => {
    const counter = latest // a plain counter, not a DOM node
    load()
    return () => {
      counter.current++ // unmounted: ignore whatever is still in flight
    }
  }, [load])

  return (
    <section>
      <div className="profile">
        <Avatar name={person.first_name} photoUrl={person.photo_url} />
        <h2 className="person-title">{fullName(person)}</h2>
      </div>

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
        <p className="hint wish-list-state">Поки що тут немає бажань</p>
      )}
      {wishes && wishes.length > 0 && (
        <div className="wish-list person-wishes">
          {wishes.map((w) => (
            <WishCard key={w.id} wish={w} />
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
