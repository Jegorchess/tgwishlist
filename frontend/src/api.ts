import { authHeader } from './telegram'

export interface Me {
  telegram_id: number
  first_name: string
  username: string | null
  start_param: string | null
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { Authorization: authHeader(), 'Content-Type': 'application/json', ...init.headers },
  })
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
  return resp.json() as Promise<T>
}

export const api = {
  me: () => request<Me>('/api/me'),
}
