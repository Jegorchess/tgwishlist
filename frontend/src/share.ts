import { api, type Wish } from './api'
import { haptic, openTelegramLink } from './telegram'
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

export function shareList(): Promise<void> {
  return shareMyList('🎁 Мої хотєлки')
}

export function shareWish(wish: Wish): Promise<void> {
  const price = wish.price !== null ? ` — ${formatPrice(wish.price)}` : ''
  return shareMyList(`🎁 Хочу: ${wish.title}${price}`)
}

/** `?person=12` in the Mini App URL: opened from a shared link via the bot. */
export function sharedPersonId(): number | null {
  const raw = new URLSearchParams(window.location.search).get('person')
  return raw && /^\d{1,10}$/.test(raw) ? Number(raw) : null
}
