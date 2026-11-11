// Validation rules of the "add wish" form. They mirror the backend (app/api/wishes.py).
import type { Priority } from './api'

export const TITLE_MAX = 200
export const DESCRIPTION_MAX = 1000
export const URL_MAX = 2000
export const PHOTO_MAX_BYTES = 10 * 1024 * 1024
const PRICE_MAX = 99_999_999.99
const PHOTO_EXTENSIONS = /\.(jpe?g|png|webp|heic|heif)$/i
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']

export const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 1, label: 'Дуже хочу' },
  { value: 2, label: 'Хочу' },
  { value: 3, label: 'Було б непогано' },
]

export interface WishFormValues {
  title: string
  price: string
  priority: Priority
  url: string
  description: string
  photo: File | null
}

export type WishFormErrors = Partial<Record<keyof WishFormValues, string>>

export const emptyWishForm: WishFormValues = {
  title: '',
  price: '',
  priority: 2,
  url: '',
  description: '',
  photo: null,
}

/** "12,50" -> "12.50"; returns null when the value is not a valid price. */
export function normalizePrice(raw: string): string | null {
  const value = raw.trim().replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null
  return Number(value) <= PRICE_MAX ? value : null
}

function isHttpUrl(raw: string): boolean {
  if (/\s/.test(raw)) return false
  try {
    const url = new URL(raw)
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname)
  } catch {
    return false
  }
}

function isSupportedPhoto(file: File): boolean {
  return PHOTO_TYPES.includes(file.type) || PHOTO_EXTENSIONS.test(file.name)
}

export function validateWish(v: WishFormValues): WishFormErrors {
  const errors: WishFormErrors = {}
  const title = v.title.trim()
  if (!title) errors.title = 'Вкажи назву подарунка'
  else if (title.length > TITLE_MAX) errors.title = `Назва задовга (максимум ${TITLE_MAX} символів)`

  if (v.price.trim() && normalizePrice(v.price) === null)
    errors.price = 'Вкажи суму числом, наприклад 149,99'

  const url = v.url.trim()
  if (url.length > URL_MAX) errors.url = 'Посилання задовге'
  else if (url && !isHttpUrl(url)) errors.url = 'Посилання має починатися з https:// або http://'

  if (v.description.trim().length > DESCRIPTION_MAX)
    errors.description = `Опис задовгий (максимум ${DESCRIPTION_MAX} символів)`

  if (v.photo) {
    if (!isSupportedPhoto(v.photo)) errors.photo = 'Підтримуються лише фото JPEG, PNG, WebP або HEIC'
    else if (v.photo.size > PHOTO_MAX_BYTES) errors.photo = 'Фото завелике (максимум 10 МБ)'
  }
  return errors
}

export function toFormData(v: WishFormValues): FormData {
  const form = new FormData()
  form.append('title', v.title.trim())
  if (v.price.trim()) form.append('price', normalizePrice(v.price) ?? v.price)
  form.append('priority', String(v.priority))
  if (v.url.trim()) form.append('url', v.url.trim())
  if (v.description.trim()) form.append('description', v.description.trim())
  if (v.photo) form.append('photo', v.photo)
  return form
}
