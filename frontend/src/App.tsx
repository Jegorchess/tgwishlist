import { useCallback, useEffect, useRef, useState } from 'react'
import { ACCESS_LOST, api, type Me, type Person, type Wish } from './api'
import Avatar from './Avatar'
import { insideTelegram } from './telegram'
import AdminMenu from './AdminMenu'
import Logo from './Logo'
import MyReservations from './MyReservations'
import PeopleList from './PeopleList'
import PersonWishes from './PersonWishes'
import WishEditor from './WishEditor'
import WishList from './WishList'

type View =
  | { name: 'home' }
  | { name: 'wish-form'; wish?: Wish }
  | { name: 'person'; person: Person }
type Tab = 'mine' | 'people'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>({ name: 'home' })
  const [tab, setTab] = useState<Tab>('mine')
  const [notice, setNotice] = useState<string | null>(null)
  const [wishes, setWishes] = useState<Wish[] | null>(null)
  const [wishesError, setWishesError] = useState(false)
  const [archived, setArchived] = useState<Wish[]>([])

  const latestRequest = useRef(0)
  const listShown = useRef(false)

  const loadWishes = useCallback(() => {
    const request = ++latestRequest.current
    setWishesError(false)
    api
      .archive()
      .then((list) => request === latestRequest.current && setArchived(list))
      .catch(() => {}) // secondary block: the active list still works
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
    api
      .me()
      .then((profile) => {
        setMe(profile)
        // Everything else is closed without access (403), so don't even ask.
        if (profile.has_access) loadWishes()
      })
      .catch((e: Error) => setError(e.message))
  }, [loadWishes])

  useEffect(() => {
    const recheck = () => {
      api
        .me()
        .then((profile) => {
          setMe(profile)
          if (!profile.has_access) setView({ name: 'home' }) // the lock screen lives there
        })
        .catch(() => {})
    }
    window.addEventListener(ACCESS_LOST, recheck)
    return () => window.removeEventListener(ACCESS_LOST, recheck)
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 3000)
    return () => clearTimeout(timer)
  }, [notice])

  const goHome = useCallback(() => setView({ name: 'home' }), [])
  const openAddWish = useCallback(() => setView({ name: 'wish-form' }), [])
  const openEditWish = useCallback((wish: Wish) => setView({ name: 'wish-form', wish }), [])
  const openPerson = useCallback((person: Person) => setView({ name: 'person', person }), [])
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
    () => backToList(editing ? '✅ Зміни збережено' : '✅ Хотєлку додано'),
    [backToList, editing],
  )
  const onWishDeleted = useCallback(() => backToList('🗑 Хотєлку видалено'), [backToList])

  if (view.name === 'person') {
    return (
      <main className="app">
        <PersonWishes key={view.person.id} person={view.person} onBack={goHome} />
      </main>
    )
  }

  if (view.name === 'wish-form') {
    return (
      <main className="app">
        <WishEditor
          key={view.wish?.id ?? 'new'}
          wish={view.wish}
          onSaved={onWishSaved}
          onDeleted={onWishDeleted}
          onArchiveChanged={backToList}
          onCancel={goHome}
        />
      </main>
    )
  }

  return (
    <main className="app">
      <header className="app-header">
        <Logo />
        {me?.has_access && me.is_admin && <AdminMenu />}
      </header>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && <p className="error">Не вдалося завантажити профіль: {error}</p>}
      {!error && !me && <p className="hint">Завантаження…</p>}
      {me && !me.has_access && (
        <section className="no-access">
          <p className="no-access-icon" aria-hidden>
            🔒
          </p>
          <h2>Доступ лише за запрошенням</h2>
          <p className="hint">
            Це приватні Хотєлочки для рідних і друзів. Попроси посилання-запрошення в того, хто тебе
            сюди покликав, і відкрий його в Telegram.
          </p>
        </section>
      )}
      {me && me.has_access && (
        <>
          <div className="profile">
            <Avatar name={me.first_name} photoUrl={me.photo_url} />
            <p>Привіт, {me.first_name}!</p>
          </div>
          <div className="tabs">
            <button
              type="button"
              aria-pressed={tab === 'mine'}
              className={tab === 'mine' ? 'active' : ''}
              onClick={() => setTab('mine')}
            >
              Мої хотєлки
            </button>
            <button
              type="button"
              aria-pressed={tab === 'people'}
              className={tab === 'people' ? 'active' : ''}
              onClick={() => setTab('people')}
            >
              Хотєлки інших
            </button>
          </div>
          {tab === 'mine' ? (
            <WishList
              wishes={wishes}
              error={wishesError}
              onRetry={loadWishes}
              archived={archived}
              onAdd={openAddWish}
              onOpen={openEditWish}
            />
          ) : (
            <>
              <MyReservations onOpen={openPerson} />
              <PeopleList onOpen={openPerson} />
            </>
          )}
        </>
      )}
      {!insideTelegram && <p className="hint">Режим розробки: відкрито поза Telegram.</p>}
    </main>
  )
}
