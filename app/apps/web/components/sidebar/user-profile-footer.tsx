"use client"

import { useTheme } from "next-themes"
import { LogIn, LogOut, Sun, Moon } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth-context"

interface UserProfileFooterProps {
  onOpenAuthModal: () => void
}

export function UserProfileFooter({ onOpenAuthModal }: UserProfileFooterProps) {
  const { user, logout } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "CD"

  const isDark = resolvedTheme === "dark"

  return (
    <div className="pt-2 border-t border-sidebar-border">
      {user ? (
        <DropdownMenu>
          <DropdownMenuTrigger className="flex w-full items-center gap-2.5 p-2 text-left hover:bg-sidebar-accent transition-colors outline-none focus-visible:ring-1 focus-visible:ring-ring">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center bg-accent text-accent-foreground text-xs font-medium border border-border">
              {initials}
            </div>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-xs font-medium text-sidebar-foreground truncate">
                {user.name}
              </span>
              <span className="text-[11px] text-muted-foreground truncate">
                {user.email}
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
                <p className="text-xs font-medium text-foreground">{user.name}</p>
                <p className="text-[11px] text-muted-foreground truncate">{user.email}</p>
                <span className="mt-1 w-fit border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                  Diligence Analyst
                </span>
              </div>
            </DropdownMenuLabel>

            <DropdownMenuSeparator className="bg-border my-1" />

            <DropdownMenuItem
              onClick={() => setTheme(isDark ? "light" : "dark")}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-foreground cursor-pointer focus:bg-accent focus:text-accent-foreground"
            >
              {isDark ? (
                <>
                  <Sun className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>Switch to light mode</span>
                </>
              ) : (
                <>
                  <Moon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>Switch to dark mode</span>
                </>
              )}
            </DropdownMenuItem>

            <DropdownMenuSeparator className="bg-border my-1" />

            <DropdownMenuItem
              onClick={() => logout()}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-destructive cursor-pointer focus:bg-destructive/10 focus:text-destructive"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <button
          type="button"
          onClick={onOpenAuthModal}
          className="flex w-full items-center gap-2 p-2 text-xs font-medium text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <LogIn className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Sign in / Create account</span>
        </button>
      )}
    </div>
  )
}
