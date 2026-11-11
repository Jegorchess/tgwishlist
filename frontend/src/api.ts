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

/** Someone who has wishes and can be browsed in «Люди». */
export interface Person {
  id: number
  first_name: string
  last_name: string | null
  photo_url: string | null
  wish_count: number
}

/** 1 = «Дуже хочу», 2 = «Хочу», 3 = «Було б непогано». */
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
}

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
    throw new ApiError(resp.status, detail ?? `${resp.status} ${resp.statusText}`, detail)
  }
  return resp
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await send(path, init)).json() as Promise<T>
}

export const api = {
  me: () => request<Me>('/api/me'),
  /** Admin only. */
  invite: () => request<{ link: string }>('/api/invite'),
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
  personWishes: (userId: number) => request<Wish[]>(`/api/people/${userId}/wishes`),
  /** Own wishes, already sorted: priority first, newest first. */
  myWishes: () => request<Wish[]>('/api/wishes'),
  /** Photos need the auth header, so they are fetched as a Blob rather than via <img src>. */
  wishPhoto: async (id: number, version: string) =>
    (await send(`/api/wishes/${id}/photo?v=${encodeURIComponent(version)}`)).blob(),
}
