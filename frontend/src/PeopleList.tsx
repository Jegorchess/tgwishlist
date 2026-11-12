import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Person } from './api'
import Avatar from './Avatar'

/** "1 хотєлка", "3 хотєлки", "5 хотєлок", "21 хотєлка", "12 хотєлок" */
export function wishCountLabel(n: number): string {
  const lastTwo = n % 100
  const last = n % 10
  let word = 'хотєлок'
  if (lastTwo < 11 || lastTwo > 14) {
    if (last === 1) word = 'хотєлка'
    else if (last >= 2 && last <= 4) word = 'хотєлки'
  }
  return `${n} ${word}`
}

export function fullName(p: { first_name: string; last_name: string | null }): string {
  return [p.first_name, p.last_name].filter(Boolean).join(' ')
}

export default function PeopleList({ onOpen }: { onOpen: (person: Person) => void }) {
  const [people, setPeople] = useState<Person[] | null>(null)
  const [error, setError] = useState(false)

  const latest = useRef(0)

  const load = useCallback(() => {
    const request = ++latest.current
    setError(false)
    setPeople(null)
    api
      .people()
      .then((list) => request === latest.current && setPeople(list))
      .catch(() => request === latest.current && setError(true))
  }, [])

  useEffect(() => {
    const counter = latest // a plain counter, not a DOM node
    load()
    return () => {
      counter.current++ // unmounted: ignore whatever is still in flight
    }
  }, [load])

  if (error) {
    return (
      <section className="wish-list-state">
        <p className="error">Не вдалося завантажити список людей.</p>
        <button type="button" className="secondary" onClick={load}>
          Спробувати ще раз
        </button>
      </section>
    )
  }

  if (people === null) {
    return (
      <section className="wish-list-state">
        <div className="spinner" role="status" aria-label="Завантаження" />
      </section>
    )
  }

  if (people.length === 0) {
    return (
      <section className="wish-list-state">
        <p className="hint">Тут з'являться рідні та друзі, коли додадуть свої хотєлки</p>
      </section>
    )
  }

  return (
    <ul className="people-list">
      {people.map((p) => (
        <li key={p.id}>
          <button type="button" className="person-row" onClick={() => onOpen(p)}>
            <Avatar name={p.first_name} photoUrl={p.photo_url} size={44} />
            <span className="person-name">{fullName(p)}</span>
            <span className="hint person-count">{wishCountLabel(p.wish_count)}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
