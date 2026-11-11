// Thin typed wrapper around the official telegram-web-app.js script (loaded in index.html).

interface WebAppUser {
  id: number
  first_name: string
  username?: string
}

interface WebApp {
  initData: string
  initDataUnsafe: { user?: WebAppUser; start_param?: string }
  colorScheme: 'light' | 'dark'
  ready(): void
  expand(): void
}

declare global {
  interface Window {
    Telegram?: { WebApp: WebApp }
  }
}

export const webApp: WebApp | undefined = window.Telegram?.WebApp

/** True when opened inside Telegram (initData is present). */
export const insideTelegram = Boolean(webApp?.initData)

export function initTelegram(): void {
  webApp?.ready()
  webApp?.expand()
}

/** Value for the Authorization header understood by the backend. */
export function authHeader(): string {
  if (insideTelegram) return `tma ${webApp!.initData}`
  // Local browser development: backend must run with DEV_AUTH=true.
  return 'dev local'
}
