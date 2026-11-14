import { type ReactNode, useEffect, useId, useRef } from "react"

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/**
 * Native modal <dialog>: showModal() gives a focus trap, Esc to close and an
 * inert page behind it. Focus goes back to whatever opened it on close.
 */
export function Modal({ title, onClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  // The element that had focus when the dialog opened; refocused on unmount.
  // (Never call dialog.close() in cleanup: StrictMode's simulated unmount would
  // fire the close event and dismiss the dialog straight away.)
  const opener = useRef<HTMLElement | null>(
    document.activeElement as HTMLElement | null
  )

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => {
      // Skip StrictMode's immediate re-run: only restore focus once truly gone.
      queueMicrotask(() => {
        if (!dialog?.isConnected && opener.current?.isConnected) {
          opener.current.focus()
        }
      })
    }
  }, [])

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      onClose={() => closeRef.current()}
    >
      <div className="modal-head">
        <h2 id={titleId}>{title}</h2>
        <button
          type="button"
          className="modal-x"
          aria-label="Close"
          onClick={() => ref.current?.close()}
        >
          <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  )
}
