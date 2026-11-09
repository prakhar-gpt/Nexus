"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"

export function ThemeToggle({ className }: { className?: string }) {
  const [isDark, setIsDark] = React.useState(false)

  React.useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"))
  }, [])

  function toggle() {
    const nextDark = !document.documentElement.classList.contains("dark")
    if (nextDark) {
      document.documentElement.classList.add("dark")
      localStorage.setItem("nexus_theme", "dark")
    } else {
      document.documentElement.classList.remove("dark")
      localStorage.setItem("nexus_theme", "light")
    }
    setIsDark(nextDark)
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className={`inline-flex items-center justify-center h-8 w-8 text-muted-foreground hover:text-foreground transition-colors border border-border bg-background rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer ${className || ""}`}
      aria-label="Toggle theme"
      title="Toggle theme (hotkey: d)"
    >
      {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
    </button>
  )
}

