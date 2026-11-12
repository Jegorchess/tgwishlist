import { authHeader } from './telegram'

export interface Me {
  id: number
  telegram_id: number
  first_name: string
  last_name: string | null
  username: string | null
  language_code: string | null
  photo_url: string | null
  start_param: string | null
  /** Joined via the invite link (or is an admin). Without it every other call returns 403. */
  has_access: boolean
  is_admin: boolean
}

/** Admin view of someone who joined via the invite link. */
export interface Member {
  telegram_id: number
  first_name: string
  last_name: string | null
  photo_url: string | null
  granted_at: string
  revoked: boolean
  is_admin: boolean
}

/** Visible only to people other than the wish's owner. */
export interface Reservation {
  mine: boolean
  by_name: string
}

/** A wish in someone else's list (with its reservation, if any). */
export interface OthersWish extends Wish {
  reservation: Reservation | null
}

export interface MyReservation {
  wish: OthersWish
  owner: Person
}

/** Someone who has wishes and can be browsed in «Хотєлки інших». */
export interface Person {
  id: number
  first_name: string
  last_name: string | null
  photo_url: string | null
  wish_count: number
}

/** 1 = «Жесть як хочу», 2 = «Було б круто», 3 = «Хочу, але переживу». */
export type Priority = 1 | 2 | 3

export interface Wish {
  id: number
  title: string
  /** Decimal as a string, e.g. "249.99" (PLN). */
  price: string | null
  priority: Priority
  url: string | null
  description: string | null
  has_photo: boolean
  /** Changes when the photo is replaced; use it to refetch. */
  photo_version: string | null
  created_at: string
  /** Set when the owner marked it as received (it's in the archive). */
  received_at?: string | null
}

/** Fired on any 403: the app re-reads /api/me and shows the lock screen if needed. */
export const ACCESS_LOST = 'wishlist:access-lost'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Human-readable `detail` from the backend, when it is a plain string. */
    readonly detailText: string | null = null,
  ) {
    super(message)
  }
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { Authorization: authHeader() }
  // For FormData the browser sets the multipart Content-Type with its boundary itself.
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'

  const resp = await fetch(path, { ...init, headers: { ...headers, ...init.headers } })
  if (!resp.ok) {
    let detail: string | null = null
    try {
      const body = await resp.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Not JSON: keep the status text.
    }
    // 403 means access was taken away while the app was open: let the app re-check.
    if (resp.status === 403) window.dispatchEvent(new Event(ACCESS_LOST))
    throw new ApiError(resp.status, detail ?? `${resp.status} ${resp.statusText}`, detail)
  }
  return resp
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await send(path, init)).json() as Promise<T>
}

export const api = {
  me: () => request<Me>('/api/me'),
  /** AF-1: what a shop page says about the product (any field may be null). */
  linkPreview: (url: string) =>
    request<{ title: string | null; price: string | null; image_url: string | null }>(
      '/api/link-preview',
      { method: 'POST', body: JSON.stringify({ url }) },
    ),
  /** The page's image, proxied by the server (shops don't allow cross-origin fetches). */
  linkPreviewImage: async (url: string) =>
    (await send(`/api/link-preview/image?url=${encodeURIComponent(url)}`)).blob(),
  /** Admin only. */
  invite: () => request<{ link: string }>('/api/invite'),
  members: () => request<Member[]>('/api/admin/members'),
  revokeMember: async (telegramId: number) => {
    await send(`/api/admin/members/${telegramId}/revoke`, { method: 'POST' })
  },
  restoreMember: async (telegramId: number) => {
    await send(`/api/admin/members/${telegramId}/restore`, { method: 'POST' })
  },
  regenerateInvite: () => request<{ link: string }>('/api/invite/regenerate', { method: 'POST' }),
  /** Fields: title, price, priority, url, description, photo (optional file). */
  createWish: (form: FormData) => request<Wish>('/api/wishes', { method: 'POST', body: form }),
  /** Replaces all fields; send remove_photo=true to drop the photo. */
  updateWish: (id: number, form: FormData) =>
    request<Wish>(`/api/wishes/${id}`, { method: 'PATCH', body: form }),
  deleteWish: async (id: number) => {
    await send(`/api/wishes/${id}`, { method: 'DELETE' })
  },
  /** Everyone with wishes except me, sorted by name. */
  people: () => request<Person[]>('/api/people'),
  /** Someone else's wishes (read-only), sorted like my own. */
  personWishes: (userId: number) => request<OthersWish[]>(`/api/people/${userId}/wishes`),
  /** «Я дарую». 409 if someone else was faster. */
  reserve: (wishId: number) =>
    request<OthersWish>(`/api/wishes/${wishId}/reservation`, { method: 'POST' }),
  cancelReservation: async (wishId: number) => {
    await send(`/api/wishes/${wishId}/reservation`, { method: 'DELETE' })
  },
  myReservations: () => request<MyReservation[]>('/api/reservations'),
  /** My received wishes, newest first. */
  archive: () => request<Wish[]>('/api/wishes/archive'),
  markReceived: (id: number) => request<Wish>(`/api/wishes/${id}/received`, { method: 'POST' }),
  restoreWish: (id: number) => request<Wish>(`/api/wishes/${id}/restore`, { method: 'POST' }),
  /** A t.me link to my list (opens the bot, which opens the app on my wishes). */
  shareLink: () => request<{ link: string }>('/api/share-link'),
  /** Own wishes, already sorted: priority first, newest first. */
  myWishes: () => request<Wish[]>('/api/wishes'),
  /** Photos need the auth header, so they are fetched as a Blob rather than via <img src>. */
  wishPhoto: async (id: number, version: string) =>
    (await send(`/api/wishes/${id}/photo?v=${encodeURIComponent(version)}`)).blob(),
}
