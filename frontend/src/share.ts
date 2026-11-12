import { api, type Wish } from './api'
import { haptic, openTelegramLink, webApp } from './telegram'
import { formatPrice } from './WishCard'

/** Open Telegram's "share to chat" picker with my list link and a text. */
async function shareMyList(text: string): Promise<void> {
  try {
    const { link } = await api.shareLink()
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`
    openTelegramLink(url)
  } catch {
    haptic('error')
    window.alert('Не вдалося поділитися. Перевір з’єднання і спробуй ще раз.')
  }
}

export function shareWish(wish: Wish): Promise<void> {
  const price = wish.price !== null ? ` — ${formatPrice(wish.price)}` : ''
  return shareMyList(`🎁 Хочу: ${wish.title}${price}`)
}

/**
 * Whose list to open: `startapp=list_12` (link opened the Mini App directly) or
 * `?person=12` (opened from the bot's button).
 */
export function sharedPersonId(): number | null {
  const startParam = webApp?.initDataUnsafe.start_param ?? ''
  const fromStart = /^list_(\d{1,10})$/.exec(startParam)
  if (fromStart) return Number(fromStart[1])
  const raw = new URLSearchParams(window.location.search).get('person')
  return raw && /^\d{1,10}$/.test(raw) ? Number(raw) : null
}
