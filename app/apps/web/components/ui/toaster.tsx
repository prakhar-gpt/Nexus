"use client"

import React from "react"
import { useToast, clearToast } from "@/lib/toast"
import { AlertCircle, X } from "lucide-react"

export function Toaster() {
  const toast = useToast()

  if (!toast) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-5 right-5 z-50 flex max-w-sm items-center justify-between gap-3 border border-border bg-popover px-3.5 py-2.5 text-xs text-foreground shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-150"
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span>{toast}</span>
      </div>
      <button
        type="button"
        aria-label="Close notification"
        onClick={clearToast}
        className="p-0.5 text-muted-foreground hover:text-foreground transition-colors"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  )
}

