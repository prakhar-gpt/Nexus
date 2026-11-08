"use client"

import { useEffect, useRef, useImperativeHandle, forwardRef } from "react"
import { ArrowUp, Square } from "lucide-react"

export interface ComposerHandle {
  focus: () => void
}

interface ComposerProps {
  draft: string
  busy: boolean
  lastQuestion?: string
  placeholder?: string
  onDraft: (value: string) => void
  onAsk: (question: string) => void
  onAbort?: () => void
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  {
    draft,
    busy,
    lastQuestion,
    placeholder = "Ask a question about Superstore…",
    onDraft,
    onAsk,
    onAbort,
  },
  ref
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({
    focus: () => {
      textareaRef.current?.focus()
    },
  }))

  // Auto-resize textarea from 1 to 8 lines
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    const maxHeight = 8 * 24 // ~8 lines
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [draft])

  // Global '/' hotkey to focus composer when not typing in another input
  useEffect(() => {
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const active = document.activeElement
        const isInput =
          active instanceof HTMLInputElement ||
          active instanceof HTMLTextAreaElement ||
          active instanceof HTMLSelectElement ||
          active?.getAttribute("contenteditable") === "true"

        if (!isInput) {
          e.preventDefault()
          textareaRef.current?.focus()
        }
      }
    }

    window.addEventListener("keydown", handleGlobalKeyDown)
    return () => window.removeEventListener("keydown", handleGlobalKeyDown)
  }, [])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter newline
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!busy && draft.trim()) {
        onAsk(draft.trim())
      }
      return
    }

    // Up arrow in empty composer recalls the last question
    if (e.key === "ArrowUp" && draft === "" && lastQuestion) {
      e.preventDefault()
      onDraft(lastQuestion)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) {
      onAbort?.()
    } else if (draft.trim()) {
      onAsk(draft.trim())
    }
  }

  const canSend = draft.trim().length > 0 && !busy

  return (
    <div className="w-full max-w-[720px] mx-auto px-4 pb-4">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col border border-border bg-card transition-all focus-within:border-primary focus-within:ring-3 focus-within:ring-primary/15"
      >
        <div className="relative flex items-end p-2.5">
          <textarea
            ref={textareaRef}
            value={draft}
            rows={1}
            placeholder={placeholder}
            aria-label="Ask a question"
            disabled={busy}
            onChange={(e) => onDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[38px] max-h-[192px] w-full resize-none bg-transparent pr-10 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground outline-none disabled:opacity-60"
          />

          <div className="absolute right-2.5 bottom-2.5">
            {busy ? (
              <button
                type="button"
                onClick={onAbort}
                aria-label="Stop generating"
                className="flex h-7 w-7 items-center justify-center bg-foreground text-background transition-opacity hover:opacity-90"
                title="Stop generating"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!canSend}
                aria-label="Send question"
                className={`flex h-7 w-7 items-center justify-center transition-colors rounded-full ${
                  canSend
                    ? "bg-foreground text-background hover:opacity-90 cursor-pointer"
                    : "bg-muted text-muted-foreground/50 cursor-not-allowed"
                }`}
                title="Send (Enter)"
              >
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </form>

      <p className="mt-2 text-center text-[11px] text-muted-foreground select-none">
        Answers are checked against query results. Verify before sharing.
      </p>
    </div>
  )
})

