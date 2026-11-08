"use client"

import { LogIn, LogOut } from "lucide-react"
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

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "G"

  return (
    <div className="pt-2 border-t border-sidebar-border/60">
      {user ? (
        <DropdownMenu>
          <DropdownMenuTrigger className="flex w-full items-center justify-between p-1.5 rounded hover:bg-accent/40 transition-colors text-left focus:outline-none">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-xs border border-primary/20">
                {initials}
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-medium text-foreground truncate">{user.name}</span>
                <span className="text-[10px] text-muted-foreground truncate">{user.email}</span>
              </div>
            </div>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="start" side="top" className="w-56 mb-1">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-xs font-semibold leading-none">{user.name}</p>
                <p className="text-[11px] leading-none text-muted-foreground">{user.email}</p>
                <p className="text-[10px] text-primary pt-0.5">{user.role}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => logout()}
              className="text-xs text-destructive focus:text-destructive cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5 mr-2" />
              Log Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <button
          type="button"
          onClick={onOpenAuthModal}
          className="flex w-full items-center gap-2 p-1.5 rounded text-xs font-medium text-primary hover:bg-primary/5 transition-colors"
        >
          <LogIn className="h-4 w-4" />
          <span>Sign In / Create Account</span>
        </button>
      )}
    </div>
  )
}
