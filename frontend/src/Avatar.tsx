import { useState } from 'react'

interface Props {
  name: string
  photoUrl: string | null
  size?: number
}

/** Telegram avatar with the first letter of the name as a fallback. */
export default function Avatar({ name, photoUrl, size = 48 }: Props) {
  const [failed, setFailed] = useState(false)
  const style = { width: size, height: size, fontSize: size * 0.4 }

  return photoUrl && !failed ? (
    <img className="avatar" style={style} src={photoUrl} alt="" onError={() => setFailed(true)} />
  ) : (
    <div className="avatar avatar-fallback" style={style} aria-hidden>
      {name.charAt(0).toUpperCase() || '?'}
    </div>
  )
}
