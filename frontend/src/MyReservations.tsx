import { useEffect, useRef, useState } from 'react'
import { api, type MyReservation, type Person } from './api'
import { fullName } from './PeopleList'
import { formatPrice } from './WishCard'

/** «Я дарую»: what I've promised to gift. Hidden when there's nothing. */
export default function MyReservations({ onOpen }: { onOpen: (person: Person) => void }) {
  const [items, setItems] = useState<MyReservation[]>([])
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    api
      .myReservations()
      .then((list) => mounted.current && setItems(list))
      // Secondary block: the people list below still works, so just note the failure.
      .catch((err) => console.warn('Failed to load reservations', err))
    return () => {
      mounted.current = false
    }
  }, [])

  if (items.length === 0) return null

  return (
    <section className="my-reservations">
      <h2 className="section-title">🎁 Я дарую</h2>
      <ul className="people-list">
        {items.map(({ wish, owner }) => (
          <li key={wish.id}>
            <button type="button" className="person-row" onClick={() => onOpen(owner)}>
              <span className="person-name">
                {wish.title}
                <small className="hint reservation-owner">для {fullName(owner)}</small>
              </span>
              {wish.price !== null && (
                <span className="hint person-count">{formatPrice(wish.price)}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
