import { useCallback, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type ToastItem = {
  id: number
  type: 'success' | 'error' | 'info'
  message: string
}

let nextId = 0

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timerRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timerRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timerRef.current.delete(id)
    }
  }, [])

  const show = useCallback(
    (type: ToastItem['type'], message: string) => {
      const id = nextId++
      setToasts((prev) => [...prev, { id, type, message }])
      const timer = setTimeout(() => remove(id), 3000)
      timerRef.current.set(id, timer)
    },
    [remove],
  )

  const toastHolder: ReactNode =
    toasts.length > 0 ? (
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`} onClick={() => remove(t.id)}>
            {t.message}
          </div>
        ))}
      </div>
    ) : null

  return {
    success: (msg: string) => show('success', msg),
    error: (msg: string) => show('error', msg),
    info: (msg: string) => show('info', msg),
    holder: toastHolder,
  }
}
