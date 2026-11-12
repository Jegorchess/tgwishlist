import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type PointerEvent,
} from 'react'
import InviteCard from './InviteCard'
import MembersCard from './MembersCard'
import { useBackButton } from './telegram'

/** ☰ in the header: admin tools (invite link, members) live here, off the home screen. */
export default function AdminMenu() {
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])

  return (
    <>
      <button
        type="button"
        className="burger"
        aria-label="Меню керування"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        ☰
      </button>
      {open && <MenuPanel onClose={close} />}
    </>
  )
}

function MenuPanel({ onClose }: { onClose: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const pressStartedOnOverlay = useRef(false)

  useBackButton(onClose)

  useEffect(() => {
    // Focus into the dialog, back to ☰ afterwards; lock the page behind it.
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus()
    }
  }, [onClose])

  // Close on a tap on the dim area only — not when e.g. selecting text drags outside.
  const onPointerDown = (e: PointerEvent) => {
    pressStartedOnOverlay.current = e.target === e.currentTarget
  }
  const onClick = (e: MouseEvent) => {
    if (pressStartedOnOverlay.current && e.target === e.currentTarget) onClose()
  }

  return (
    <div className="menu-overlay" onPointerDown={onPointerDown} onClick={onClick}>
      <aside className="menu-panel" role="dialog" aria-modal="true" aria-label="Керування">
        <header className="menu-header">
          <h2>Керування</h2>
          <button
            ref={closeButton}
            type="button"
            className="menu-close"
            aria-label="Закрити"
            onClick={onClose}
          >
            ✕
          </button>
        </header>
        <InviteCard />
        <MembersCard />
      </aside>
    </div>
  )
}
