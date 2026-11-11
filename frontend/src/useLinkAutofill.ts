import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { isHttpUrl, type WishFormValues } from './wishForm'

export type AutofillStatus = 'idle' | 'loading' | 'failed'

const DEBOUNCE_MS = 700

function extensionFor(type: string): string {
  return { 'image/png': 'png', 'image/webp': 'webp', 'image/heic': 'heic' }[type] ?? 'jpg'
}

/**
 * AF-1: when a link is pasted into the "add wish" form, fetch the page's title, PLN price
 * and photo, and fill only the fields that are still empty.
 */
export function useLinkAutofill(
  url: string,
  enabled: boolean,
  setValues: (update: (prev: WishFormValues) => WishFormValues) => void,
): AutofillStatus {
  const [status, setStatus] = useState<AutofillStatus>('idle')
  const lastTried = useRef<string | null>(null)
  const latest = useRef(0)

  useEffect(() => {
    // The link changed: whatever is in flight for the old one must not fill the form.
    latest.current++
    setStatus('idle')
    const link = url.trim()
    if (!enabled || !isHttpUrl(link) || link === lastTried.current) return
    const timer = setTimeout(async () => {
      lastTried.current = link
      const request = ++latest.current
      const stale = () => request !== latest.current
      setStatus('loading')
      try {
        const found = await api.linkPreview(link)
        if (stale()) return
        let photo: File | null = null
        if (found.image_url) {
          try {
            const blob = await api.linkPreviewImage(found.image_url)
            photo = new File([blob], `photo.${extensionFor(blob.type)}`, { type: blob.type })
          } catch {
            // No photo is fine: title and price are still useful.
          }
        }
        if (stale()) return
        // Only empty fields: never overwrite what the user has typed meanwhile.
        setValues((prev) => ({
          ...prev,
          title: prev.title.trim() ? prev.title : (found.title ?? prev.title),
          price:
            prev.price.trim() || found.price === null ? prev.price : found.price.replace('.', ','),
          photo: prev.photo || prev.keepPhoto ? prev.photo : photo,
        }))
        setStatus(found.title || found.price || photo ? 'idle' : 'failed')
      } catch {
        if (!stale()) setStatus('failed')
      }
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [url, enabled, setValues])

  return status
}
