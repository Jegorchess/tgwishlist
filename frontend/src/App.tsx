import { useEffect, useState } from 'react'
import { api, type Me } from './api'
import { insideTelegram } from './telegram'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [avatarFailed, setAvatarFailed] = useState(false)

  useEffect(() => {
    api.me().then(setMe).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="app">
      <h1>🎁 Сімейний вішліст</h1>
      {error && <p className="error">Не вдалося завантажити профіль: {error}</p>}
      {!error && !me && <p className="hint">Завантаження…</p>}
      {me && (
        <div className="profile">
          {me.photo_url && !avatarFailed ? (
            <img
              className="avatar"
              src={me.photo_url}
              alt=""
              onError={() => setAvatarFailed(true)}
            />
          ) : (
            <div className="avatar avatar-fallback">{me.first_name.charAt(0) || '?'}</div>
          )}
          <p>Привіт, {me.first_name}!</p>
        </div>
      )}
      {!insideTelegram && (
        <p className="hint">Режим розробки: відкрито поза Telegram.</p>
      )}
    </main>
  )
}
