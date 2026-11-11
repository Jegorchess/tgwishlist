import { useState } from 'react'
import { api, ApiError, type OthersWish, type Reservation } from './api'
import { confirmDialog, haptic } from './telegram'

interface Props {
  wish: OthersWish
  /** The reservation changed (null = free again). */
  onChange: (reservation: Reservation | null) => void
  /** Someone else was faster: the list should be reloaded. */
  onConflict: () => void
}

/** «Я дарую» on a card in someone else's list. */
export default function ReservationControl({ wish, onChange, onConflict }: Props) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const reservation = wish.reservation

  async function reserve() {
    setBusy(true)
    setMessage(null)
    try {
      const updated = await api.reserve(wish.id)
      haptic('success')
      onChange(updated.reservation)
    } catch (err) {
      haptic('error')
      if (err instanceof ApiError && err.status === 409) {
        setMessage('Хтось щойно забронював це бажання')
        onConflict()
      } else if (err instanceof ApiError && err.status === 404) {
        onConflict() // the wish was just deleted: the reloaded list won't have it
      } else setMessage('Не вдалося забронювати. Спробуй ще раз.')
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    setMessage(null)
    if (!(await confirmDialog(`Скасувати бронь «${wish.title}»?`, 'Скасувати бронь'))) return
    setBusy(true)
    try {
      await api.cancelReservation(wish.id)
      onChange(null)
    } catch (err) {
      // 404: there was nothing to cancel any more; show the actual state.
      if (err instanceof ApiError && err.status === 404) onConflict()
      else setMessage('Не вдалося скасувати. Спробуй ще раз.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="reservation">
      {!reservation && (
        <button type="button" className="reserve-button" onClick={reserve} disabled={busy}>
          🎁 Я дарую
        </button>
      )}
      {reservation?.mine && (
        <div className="reservation-row">
          <span className="reservation-mine">✅ Ти даруєш</span>
          <button type="button" className="link" onClick={cancel} disabled={busy}>
            Скасувати
          </button>
        </div>
      )}
      {reservation && !reservation.mine && (
        <span className="reservation-taken">🎁 Вже дарує {reservation.by_name}</span>
      )}
      {message && <small className="error">{message}</small>}
    </div>
  )
}
