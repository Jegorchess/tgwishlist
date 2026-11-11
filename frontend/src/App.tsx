import { useCallback, useEffect, useRef, useState } from 'react'
import AddWishForm from './AddWishForm'
import { api, type Me, type Wish } from './api'
import { insideTelegram } from './telegram'
import WishList from './WishList'

type View = 'home' | 'add-wish'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [avatarFailed, setAvatarFailed] = useState(false)
  const [view, setView] = useState<View>('home')
  const [notice, setNotice] = useState<string | null>(null)
  const [wishes, setWishes] = useState<Wish[] | null>(null)
  const [wishesError, setWishesError] = useState(false)

  const latestRequest = useRef(0)
  const listShown = useRef(false)

  const loadWishes = useCallback(() => {
    const request = ++latestRequest.current
    setWishesError(false)
    api
      .myWishes()
      .then((list) => {
        if (request !== latestRequest.current) return // a newer request is in flight
        listShown.current = true
        setWishes(list)
      })
      .catch(() => {
        if (request !== latestRequest.current) return
        // Keep a list that is already on screen; only show the error state on first load.
        if (listShown.current) setNotice('⚠️ Не вдалося оновити список')
        else setWishesError(true)
      })
  }, [])

  useEffect(() => {
    api.me().then(setMe).catch((e: Error) => setError(e.message))
    loadWishes()
  }, [loadWishes])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 3000)
    return () => clearTimeout(timer)
  }, [notice])

  const goHome = useCallback(() => setView('home'), [])
  const openAddWish = useCallback(() => setView('add-wish'), [])
  const onWishSaved = useCallback(() => {
    setNotice('✅ Бажання додано')
    setView('home')
    loadWishes() // the server knows the right place of the new wish in the sorted list
  }, [loadWishes])

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
          {notice}
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
          <WishList
            wishes={wishes}
            error={wishesError}
            onRetry={loadWishes}
            onAdd={openAddWish}
          />
        </>
      )}
      {!insideTelegram && <p className="hint">Режим розробки: відкрито поза Telegram.</p>}
    </main>
  )
}
