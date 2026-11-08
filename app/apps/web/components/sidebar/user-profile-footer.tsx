"use client"

import React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { LogIn, LogOut, Sun } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useSession } from "@/lib/auth/provider"
import { useChatStore } from "@/lib/chat-store"
import { clearResourceCache } from "@/lib/use-resource"

export function UserProfileFooter() {
  const router = useRouter()
  const { session, signOut } = useSession()
  const { clearAll } = useChatStore()

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains("dark")
    if (isDark) {
      document.documentElement.classList.remove("dark")
      localStorage.setItem("nexus_theme", "light")
    } else {
      document.documentElement.classList.add("dark")
      localStorage.setItem("nexus_theme", "dark")
    }
  }

  async function handleLogOut() {
    clearAll()
    clearResourceCache()
    await signOut()
    router.replace("/login")
  }

  const initials = session?.name
    ? session.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "DA"

  return (
    <div className="pt-2 border-t border-sidebar-border">
      {session ? (
        <DropdownMenu>
          <DropdownMenuTrigger className="flex w-full items-center gap-2.5 p-2 text-left hover:bg-sidebar-accent transition-colors outline-none focus-visible:ring-1 focus-visible:ring-ring">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center bg-accent text-accent-foreground text-xs font-medium border border-border">
              {initials}
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-medium text-sidebar-foreground truncate">
                {session.name}
              </span>
              <span className="text-[11px] text-muted-foreground truncate">
                {session.email}
              </span>
            </div>
          </DropdownMenuTrigger>

          <DropdownMenuContent
            align="start"
            side="top"
            className="w-56 mb-1 rounded-[var(--radius)] border border-border bg-popover p-1 shadow-none"
          >
            <DropdownMenuLabel className="font-normal px-2 py-1.5">
              <div className="flex flex-col gap-1">
                <p className="text-xs font-medium text-foreground">{session.name}</p>
                <p className="text-[11px] text-muted-foreground truncate">{session.email}</p>
                <span className="mt-1 w-fit border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                  {session.role}
                </span>
              </div>
            </DropdownMenuLabel>

            <DropdownMenuSeparator className="bg-border my-1" />

            <DropdownMenuItem
              onClick={toggleTheme}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-foreground cursor-pointer focus:bg-accent focus:text-accent-foreground"
            >
              <Sun className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Toggle theme</span>
            </DropdownMenuItem>

            <DropdownMenuSeparator className="bg-border my-1" />

            <DropdownMenuItem
              onClick={handleLogOut}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-destructive cursor-pointer focus:bg-destructive/10 focus:text-destructive"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <Link
          href="/login"
          className="flex w-full items-center gap-2 p-2 text-xs font-medium text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <LogIn className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Sign in</span>
        </Link>
      )}
    </div>
  )
}
