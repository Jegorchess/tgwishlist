import type { Wish } from './api'

/** Search appears only when a list is long enough to need it. */
export const SEARCH_THRESHOLD = 5

/** Case-insensitive match on title and description; every word must match. */
export function filterWishes<T extends Wish>(wishes: T[], query: string): T[] {
  const words = query.toLocaleLowerCase('uk').split(/\s+/).filter(Boolean)
  if (words.length === 0) return wishes
  return wishes.filter((w) => {
    const text = `${w.title} ${w.description ?? ''}`.toLocaleLowerCase('uk')
    return words.every((word) => text.includes(word))
  })
}

export function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="search-box">
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="🔍 Пошук за назвою чи описом"
        aria-label="Пошук бажань"
      />
    </div>
  )
}
