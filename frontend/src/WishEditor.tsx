import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Wish } from './api'
import { confirmDialog, haptic, useBackButton } from './telegram'
import { useLinkAutofill } from './useLinkAutofill'
import { useWishPhoto } from './WishCard'
import {
  DESCRIPTION_MAX,
  PRIORITIES,
  TITLE_MAX,
  emptyWishForm,
  fromWish,
  toFormData,
  validateWish,
  type WishFormErrors,
  type WishFormValues,
} from './wishForm'

interface Props {
  /** The wish being edited; omitted when adding a new one. */
  wish?: Wish
  onSaved: (wish: Wish) => void
  onDeleted: () => void
  onCancel: () => void
}

export default function WishEditor({ wish, onSaved, onDeleted, onCancel }: Props) {
  const editing = wish !== undefined
  const [values, setValues] = useState<WishFormValues>(() => (wish ? fromWish(wish) : emptyWishForm))
  const existingPhoto = useWishPhoto(wish)
  // Autofill only when adding: an existing wish's fields are already chosen.
  const autofill = useLinkAutofill(values.url, !editing, setValues)
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
      const form = toFormData(values, editing)
      const saved = wish ? await api.updateWish(wish.id, form) : await api.createWish(form)
      haptic('success')
      onSaved(saved)
    } catch (err) {
      haptic('error')
      if (err instanceof ApiError && err.status === 413)
        setErrors({ photo: 'Фото завелике (максимум 10 МБ)' })
      else if (err instanceof ApiError && err.status === 422 && err.detailText)
        // A plain-text reason comes only from the photo check (e.g. "Файл не є зображенням").
        setErrors({ photo: err.detailText })
      else if (err instanceof ApiError && err.status === 404)
        setSubmitError('Цього бажання вже немає. Повернись до списку.')
      else if (err instanceof ApiError && err.status === 422)
        setSubmitError('Сервер не прийняв дані. Перевір поля і спробуй ще раз.')
      else setSubmitError('Не вдалося зберегти. Перевір з’єднання і спробуй ще раз.')
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!wish) return
    setSaving(true) // also blocks a second tap while the dialog is open
    setSubmitError(null)
    if (!(await confirmDialog(`Видалити бажання «${wish.title}»?`, 'Видалити'))) {
      setSaving(false)
      return
    }
    try {
      await api.deleteWish(wish.id)
      haptic('success')
      onDeleted()
    } catch (err) {
      haptic('error')
      // Already gone (e.g. deleted from another device): the goal is reached.
      if (err instanceof ApiError && err.status === 404) onDeleted()
      else setSubmitError('Не вдалося видалити. Перевір з’єднання і спробуй ще раз.')
    } finally {
      setSaving(false)
    }
  }

  const photoInput = (
    <input
      type="file"
      accept="image/*,.heic,.heif"
      hidden
      onChange={(e) => {
        set('photo', e.target.files?.[0] ?? null)
        e.target.value = ''
      }}
    />
  )

  return (
    <form className="wish-form" onSubmit={submit} noValidate>
      <h2>{editing ? 'Редагування' : 'Нове бажання'}</h2>

      <label className="field">
        <span>Назва *</span>
        <input
          value={values.title}
          onChange={(e) => set('title', e.target.value)}
          maxLength={TITLE_MAX}
          placeholder="Наприклад, навушники"
          aria-invalid={Boolean(errors.title)}
          autoFocus={!editing}
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
        {autofill === 'loading' && <small className="hint">Шукаю дані на сторінці…</small>}
        {autofill === 'no-price' && (
          <small className="hint">Ціну на сторінці не знайшли — впиши її вручну</small>
        )}
        {autofill === 'failed' && (
          <small className="hint">
            Не вдалося отримати дані з цієї сторінки — заповни вручну
          </small>
        )}
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
            <button
              type="button"
              className="link"
              onClick={() => {
                set('photo', null)
                set('keepPhoto', false)
              }}
            >
              Прибрати фото
            </button>
          </div>
        ) : values.keepPhoto ? (
          <div className="photo-preview">
            {existingPhoto ? (
              <img src={existingPhoto} alt="" />
            ) : (
              <div className="photo-name">📷 Поточне фото</div>
            )}
            <div className="photo-actions">
              <label className="link">
                Замінити фото
                {photoInput}
              </label>
              <button type="button" className="link" onClick={() => set('keepPhoto', false)}>
                Прибрати фото
              </button>
            </div>
          </div>
        ) : (
          <label className="photo-pick">
            📷 Додати фото
            {photoInput}
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

      {editing && (
        <button type="button" className="danger" onClick={remove} disabled={saving}>
          🗑 Видалити бажання
        </button>
      )}
    </form>
  )
}
