import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Wish } from './api'
import { haptic, useBackButton } from './telegram'
import {
  DESCRIPTION_MAX,
  PRIORITIES,
  TITLE_MAX,
  emptyWishForm,
  toFormData,
  validateWish,
  type WishFormErrors,
  type WishFormValues,
} from './wishForm'

interface Props {
  onSaved: (wish: Wish) => void
  onCancel: () => void
}

export default function AddWishForm({ onSaved, onCancel }: Props) {
  const [values, setValues] = useState<WishFormValues>(emptyWishForm)
  const [errors, setErrors] = useState<WishFormErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [previewFailed, setPreviewFailed] = useState(false)

  const noop = useCallback(() => {}, [])
  useBackButton(saving ? noop : onCancel)

  useEffect(() => {
    if (!values.photo) {
      setPreview(null)
      return
    }
    const url = URL.createObjectURL(values.photo)
    setPreview(url)
    setPreviewFailed(false)
    return () => URL.revokeObjectURL(url)
  }, [values.photo])

  function set<K extends keyof WishFormValues>(key: K, value: WishFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
    // Clear the field's error as soon as the user edits it.
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateWish(values)
    setErrors(found)
    setSubmitError(null)
    if (Object.values(found).some(Boolean)) {
      haptic('error')
      return
    }
    setSaving(true)
    try {
      const wish = await api.createWish(toFormData(values))
      haptic('success')
      onSaved(wish)
    } catch (err) {
      haptic('error')
      if (err instanceof ApiError && err.status === 413)
        setErrors({ photo: 'Фото завелике (максимум 10 МБ)' })
      else if (err instanceof ApiError && err.status === 422 && err.detailText)
        // A plain-text reason comes only from the photo check (e.g. "Файл не є зображенням").
        setErrors({ photo: err.detailText })
      else if (err instanceof ApiError && err.status === 422)
        setSubmitError('Сервер не прийняв дані. Перевір поля і спробуй ще раз.')
      else setSubmitError('Не вдалося зберегти. Перевір з’єднання і спробуй ще раз.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="wish-form" onSubmit={submit} noValidate>
      <h2>Нове бажання</h2>

      <label className="field">
        <span>Назва *</span>
        <input
          value={values.title}
          onChange={(e) => set('title', e.target.value)}
          maxLength={TITLE_MAX}
          placeholder="Наприклад, навушники"
          aria-invalid={Boolean(errors.title)}
          autoFocus
        />
        {errors.title && <small className="error">{errors.title}</small>}
      </label>

      <label className="field">
        <span>Вартість, zł</span>
        <input
          value={values.price}
          onChange={(e) => set('price', e.target.value)}
          inputMode="decimal"
          placeholder="149,99"
          aria-invalid={Boolean(errors.price)}
        />
        {errors.price && <small className="error">{errors.price}</small>}
      </label>

      <fieldset className="field">
        <span>Пріоритет</span>
        <div className="segmented" role="radiogroup">
          {PRIORITIES.map((p) => (
            <button
              key={p.value}
              type="button"
              role="radio"
              aria-checked={values.priority === p.value}
              className={values.priority === p.value ? 'active' : ''}
              onClick={() => set('priority', p.value)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="field">
        <span>Посилання</span>
        <input
          value={values.url}
          onChange={(e) => set('url', e.target.value)}
          type="url"
          inputMode="url"
          placeholder="https://…"
          aria-invalid={Boolean(errors.url)}
        />
        {errors.url && <small className="error">{errors.url}</small>}
      </label>

      <label className="field">
        <span>Опис</span>
        <textarea
          value={values.description}
          onChange={(e) => set('description', e.target.value)}
          rows={3}
          placeholder="Розмір, колір, модель…"
          aria-invalid={Boolean(errors.description)}
        />
        <small className="hint counter">
          {values.description.trim().length}/{DESCRIPTION_MAX}
        </small>
        {errors.description && <small className="error">{errors.description}</small>}
      </label>

      <div className="field">
        <span>Фото</span>
        {values.photo ? (
          <div className="photo-preview">
            {preview && !previewFailed ? (
              <img src={preview} alt="" onError={() => setPreviewFailed(true)} />
            ) : (
              <div className="photo-name">📷 {values.photo.name}</div>
            )}
            <button type="button" className="link" onClick={() => set('photo', null)}>
              Прибрати фото
            </button>
          </div>
        ) : (
          <label className="photo-pick">
            📷 Додати фото
            <input
              type="file"
              accept="image/*,.heic,.heif"
              hidden
              onChange={(e) => {
                set('photo', e.target.files?.[0] ?? null)
                e.target.value = ''
              }}
            />
          </label>
        )}
        {errors.photo && <small className="error">{errors.photo}</small>}
      </div>

      {submitError && <p className="error">{submitError}</p>}

      <div className="actions">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Зберігаю…' : 'Зберегти'}
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={saving}>
          Скасувати
        </button>
      </div>
    </form>
  )
}
