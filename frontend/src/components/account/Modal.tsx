import {
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
} from "react"

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])'

/**
 * showModal() makes the page inert, but Tab still leaves for the browser's own
 * UI after the last control. Wrap it so focus stays in the dialog.
 */
function trapTab(e: KeyboardEvent<HTMLDialogElement>) {
  if (e.key !== "Tab") return
  const items = [
    ...e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE),
  ].filter((el) => el.offsetParent !== null || el === document.activeElement)
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

/**
 * Native modal <dialog>: showModal() gives an inert page behind it and Esc to
 * close; trapTab keeps Tab inside. Focus goes back to the opener on close.
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
      onKeyDown={trapTab}
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
