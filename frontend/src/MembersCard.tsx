import { useCallback, useEffect, useState } from 'react'
import { api, type Member } from './api'
import Avatar from './Avatar'
import { fullName } from './PeopleList'
import { confirmDialog, haptic } from './telegram'

const dateFormat = new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'long' })

/** Admin only: who joined via the invite link, and taking access away / giving it back. */
export default function MembersCard() {
  const [members, setMembers] = useState<Member[] | null>(null)
  const [error, setError] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(() => {
    api
      .members()
      .then((list) => {
        setMembers(list)
        setError(false)
      })
      .catch(() => setError(true))
  }, [])

  useEffect(load, [load])

  async function toggle(member: Member) {
    const name = fullName(member)
    const ok = member.revoked
      ? await confirmDialog(`Повернути доступ для ${name}?`, 'Повернути', false)
      : await confirmDialog(
          `Забрати доступ у ${name}? Хотєлки цієї людини зникнуть у всіх, її броні знімуться, ` +
            'а посилання-запрошення для неї більше не працюватиме.',
          'Забрати доступ',
        )
    if (!ok) return
    setBusyId(member.telegram_id)
    try {
      if (member.revoked) await api.restoreMember(member.telegram_id)
      else await api.revokeMember(member.telegram_id)
      haptic('success')
      load()
    } catch {
      haptic('error')
      setError(true)
    } finally {
      setBusyId(null)
    }
  }

  const active = members?.filter((m) => !m.revoked) ?? []
  const blocked = members?.filter((m) => m.revoked) ?? []

  return (
    <details className="invite-card" open>
      <summary>👥 Учасники{members ? ` (${active.length})` : ''}</summary>
      {error && <p className="error">Не вдалося виконати. Спробуй ще раз.</p>}
      {!members && !error && <p className="hint">Завантаження…</p>}
      {members && members.length === 0 && (
        <p className="hint small-text">Ще ніхто не приєднався за посиланням.</p>
      )}
      {active.map((m) => row(m))}
      {blocked.length > 0 && <p className="hint members-heading">🚫 Заблоковані</p>}
      {blocked.map((m) => row(m))}
    </details>
  )

  function row(m: Member) {
    return (
        <div key={m.telegram_id} className={m.revoked ? 'member-row revoked' : 'member-row'}>
          <Avatar name={m.first_name} photoUrl={m.photo_url} size={36} />
          <span className="member-name">
            {fullName(m)}
            <small className="hint">
              {m.revoked ? '🚫 Доступ закрито' : `з ${dateFormat.format(new Date(m.granted_at))}`}
            </small>
          </span>
          {m.is_admin ? (
            <small className="hint">адмін</small>
          ) : (
            <button
              type="button"
              className={m.revoked ? 'link' : 'link danger-link'}
              onClick={() => toggle(m)}
              disabled={busyId !== null}
            >
              {m.revoked ? 'Повернути' : 'Забрати доступ'}
            </button>
          )}
        </div>
    )
  }
}
