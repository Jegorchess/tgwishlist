import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Me, type Wish } from './api'
import { insideTelegram } from './telegram'
import WishEditor from './WishEditor'
import WishList from './WishList'

type View = { name: 'home' } | { name: 'wish-form'; wish?: Wish }

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [avatarFailed, setAvatarFailed] = useState(false)
  const [view, setView] = useState<View>({ name: 'home' })
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

  const goHome = useCallback(() => setView({ name: 'home' }), [])
  const openAddWish = useCallback(() => setView({ name: 'wish-form' }), [])
  const openEditWish = useCallback((wish: Wish) => setView({ name: 'wish-form', wish }), [])
  const editing = view.name === 'wish-form' && view.wish !== undefined

  const backToList = useCallback(
    (message: string) => {
      setNotice(message)
      setView({ name: 'home' })
      loadWishes() // the server knows the right place of the wish in the sorted list
    },
    [loadWishes],
  )
  const onWishSaved = useCallback(
    () => backToList(editing ? '✅ Зміни збережено' : '✅ Бажання додано'),
    [backToList, editing],
  )
  const onWishDeleted = useCallback(() => backToList('🗑 Бажання видалено'), [backToList])

  if (view.name === 'wish-form') {
    return (
      <main className="app">
        <WishEditor
          key={view.wish?.id ?? 'new'}
          wish={view.wish}
          onSaved={onWishSaved}
          onDeleted={onWishDeleted}
          onCancel={goHome}
        />
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
            onOpen={openEditWish}
          />
        </>
      )}
      {!insideTelegram && <p className="hint">Режим розробки: відкрито поза Telegram.</p>}
    </main>
  )
}
