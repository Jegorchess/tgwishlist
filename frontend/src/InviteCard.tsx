import { useEffect, useState } from 'react'
import { api } from './api'
import { confirmDialog, haptic, openTelegramLink } from './telegram'

const SHARE_TEXT = 'Приєднуйся до наших Хотєлочок 🎁'

/** Admin only: the invite link for relatives and friends. */
export default function InviteCard() {
  const [link, setLink] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api
      .invite()
      .then((r) => setLink(r.link))
      .catch(() => setError(true))
  }, [])

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

  async function copy() {
    if (!link) return
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      haptic('success')
    } catch {
      // Clipboard can be unavailable in some webviews: let the user copy by hand.
      window.prompt('Скопіюй посилання:', link)
    }
  }

  function share() {
    if (!link) return
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(SHARE_TEXT)}`
    openTelegramLink(url)
  }

  async function regenerate() {
    setBusy(true)
    const ok = await confirmDialog(
      'Створити нове посилання? Старе перестане працювати, але ті, хто вже приєднався, доступ не втратять.',
      'Створити',
    )
    if (!ok) {
      setBusy(false)
      return
    }
    try {
      setLink((await api.regenerateInvite()).link)
      setError(false)
      haptic('success')
    } catch {
      haptic('error')
      // The server may have changed the link anyway: show whatever is current now.
      api
        .invite()
        .then((r) => setLink(r.link))
        .catch(() => setError(true))
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="invite-card" open>
      <summary>👋 Запросити рідних і друзів</summary>
      {error && <p className="error">Не вдалося отримати посилання.</p>}
      {!error && !link && <p className="hint">Завантаження…</p>}
      {link && (
        <>
          <p className="hint small-text">
            Надішли це посилання тим, кого хочеш запросити. Хто відкриє його — отримає доступ.
          </p>
          <code className="invite-link">{link}</code>
          <div className="invite-actions">
            <button type="button" className="primary" onClick={share} disabled={busy}>
              Поділитися
            </button>
            <button type="button" className="secondary" onClick={copy} disabled={busy}>
              {copied ? 'Скопійовано ✓' : 'Скопіювати'}
            </button>
          </div>
          <button type="button" className="link" onClick={regenerate} disabled={busy}>
            Створити нове посилання
          </button>
        </>
      )}
    </details>
  )
}
