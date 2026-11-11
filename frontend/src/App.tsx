import { useCallback, useEffect, useState } from 'react'
import AddWishForm from './AddWishForm'
import { api, type Me } from './api'
import { insideTelegram } from './telegram'

type View = 'home' | 'add-wish'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [avatarFailed, setAvatarFailed] = useState(false)
  const [view, setView] = useState<View>('home')
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    api.me().then(setMe).catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 3000)
    return () => clearTimeout(timer)
  }, [notice])

  const goHome = useCallback(() => setView('home'), [])
  const onWishSaved = useCallback(() => {
    setNotice('Бажання додано')
    setView('home')
  }, [])

  if (view === 'add-wish') {
    return (
      <main className="app">
        <AddWishForm onSaved={onWishSaved} onCancel={goHome} />
      </main>
    )
  }

  return (
    <main className="app">
      <h1>🎁 Сімейний вішліст</h1>
      {notice && (
        <p className="notice" role="status">
          ✅ {notice}
        </p>
      )}
      {error && <p className="error">Не вдалося завантажити профіль: {error}</p>}
      {!error && !me && <p className="hint">Завантаження…</p>}
      {me && (
        <>
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
          <button className="primary" onClick={() => setView('add-wish')}>
            ➕ Додати бажання
          </button>
        </>
      )}
      {!insideTelegram && <p className="hint">Режим розробки: відкрито поза Telegram.</p>}
    </main>
  )
}
