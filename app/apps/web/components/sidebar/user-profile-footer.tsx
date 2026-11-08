"use client"

import { LogIn, LogOut, RefreshCw } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth-context"

const SCORE_LABEL: Record<string, string> = {
  sql_correctness: "SQL",
  numeric_faithfulness: "Numbers",
  refusal_accuracy: "Refusals",
}

interface UserProfileFooterProps {
  scores: Record<string, number> | null
  runningEval: boolean
  onRunEval: () => void
  onOpenAuthModal: () => void
}

export function UserProfileFooter({
  scores,
  runningEval,
  onRunEval,
  onOpenAuthModal,
}: UserProfileFooterProps) {
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
    <div className="flex flex-col gap-2.5 pt-3 border-t border-sidebar-border/60">
      {/* Evaluation Scorecard Pill */}
      {scores ? (
        <div className="flex justify-between items-center text-[10px] tracking-wide font-mono bg-muted/40 px-2 py-1 rounded">
          {Object.entries(scores).map(([name, score]) => (
            <span key={name}>
              {SCORE_LABEL[name] ?? name}: {Math.round(score * 100)}%
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        {/* User Profile / Auth Dropdown */}
        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 p-1 -ml-1 rounded hover:bg-accent/40 transition-colors text-left focus:outline-none">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-xs border border-primary/20">
                {initials}
              </div>
              <div className="flex flex-col min-w-0 max-w-[130px]">
                <span className="text-xs font-medium text-foreground truncate">{user.name}</span>
                <span className="text-[10px] text-muted-foreground truncate">{user.email}</span>
              </div>
            </DropdownMenuTrigger>

            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-xs font-semibold leading-none">{user.name}</p>
                  <p className="text-[11px] leading-none text-muted-foreground">{user.email}</p>
                  <p className="text-[10px] text-primary pt-0.5">{user.role}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={logout}
                className="text-xs text-destructive focus:text-destructive cursor-pointer"
              >
                <LogOut className="h-3.5 w-3.5 mr-2" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <button
            type="button"
            onClick={onOpenAuthModal}
            className="flex items-center gap-2 text-xs font-medium text-primary hover:text-primary/80 transition-colors py-1"
          >
            <LogIn className="h-4 w-4" />
            <span>Sign In / Register</span>
          </button>
        )}

        {/* Eval Runner Action */}
        <button
          type="button"
          className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent/40 rounded transition-colors disabled:opacity-50"
          disabled={runningEval}
          onClick={onRunEval}
          title="Run golden set verification"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${runningEval ? "animate-spin text-primary" : ""}`} />
        </button>
      </div>
    </div>
  )
}
