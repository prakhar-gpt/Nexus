"use client"

import React, { useEffect, useRef } from "react"
import { X } from "lucide-react"

interface MobileRoomsDrawerProps {
  isOpen: boolean
  onClose: () => void
  menuButtonRef: React.RefObject<HTMLButtonElement | null>
  children: React.ReactNode
}

export function MobileRoomsDrawer({
  isOpen,
  onClose,
  menuButtonRef,
  children,
}: MobileRoomsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    const mediaQuery = window.matchMedia("(min-width: 768px)")
    function handleMediaChange(e: MediaQueryListEvent) {
      if (e.matches) onClose()
    }
    mediaQuery.addEventListener("change", handleMediaChange)

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault()
        onClose()
        return
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return

        const first = focusable[0]
        const last = focusable[focusable.length - 1]

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)

    const timer = setTimeout(() => {
      if (drawerRef.current) {
        const firstFocusable = drawerRef.current.querySelector<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        firstFocusable?.focus()
      }
    }, 0)

    return () => {
      clearTimeout(timer)
      document.body.style.overflow = prevOverflow
      mediaQuery.removeEventListener("change", handleMediaChange)
      window.removeEventListener("keydown", handleKeyDown)
      menuButtonRef.current?.focus()
    }
  }, [isOpen, onClose, menuButtonRef])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Navigation menu"
      className="fixed inset-0 z-50 flex md:hidden bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div ref={drawerRef} className="h-full w-[260px] bg-sidebar shadow-none">
        {children}
      </div>
      <button
        type="button"
        aria-label="Close menu drawer"
        onClick={onClose}
        className="flex-1 p-4 text-foreground/80 outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <X className="h-6 w-6 ml-auto" />
      </button>
    </div>
  )
}

