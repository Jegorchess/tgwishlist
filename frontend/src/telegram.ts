// Thin typed wrapper around the official telegram-web-app.js script (loaded in index.html).
import { useEffect } from 'react'

interface WebAppUser {
  id: number
  first_name: string
  username?: string
}

interface BackButton {
  show(): void
  hide(): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
}

interface WebApp {
  initData: string
  initDataUnsafe: { user?: WebAppUser; start_param?: string }
  colorScheme: 'light' | 'dark'
  ready(): void
  expand(): void
  BackButton: BackButton
  openLink(url: string): void
  HapticFeedback?: { notificationOccurred(type: 'error' | 'success' | 'warning'): void }
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

/** Show Telegram's native back button while mounted; no-op in a plain browser. */
export function useBackButton(onBack: () => void): void {
  useEffect(() => {
    const button = insideTelegram ? webApp?.BackButton : undefined
    if (!button) return
    button.show()
    button.onClick(onBack)
    return () => {
      button.offClick(onBack)
      button.hide()
    }
  }, [onBack])
}

export function haptic(type: 'error' | 'success'): void {
  webApp?.HapticFeedback?.notificationOccurred(type)
}

/** Open an external link in the browser (Telegram asks for confirmation itself). */
export function openLink(url: string): void {
  if (insideTelegram && webApp) webApp.openLink(url)
  else window.open(url, '_blank', 'noopener,noreferrer')
}
