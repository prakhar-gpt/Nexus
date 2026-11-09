"use client"

import React, { useEffect, useState } from "react"
import { Loader2, Shield, Laptop, Trash2 } from "lucide-react"
import { AuthField } from "@/components/auth/auth-field"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { authClient, AuthError } from "@/lib/auth/client"
import type { SessionInfo } from "@/lib/auth/types"
import { showToast } from "@/lib/toast"

interface AccountDialogProps {
  isOpen: boolean
  onClose: () => void
}

export function AccountDialog({ isOpen, onClose }: AccountDialogProps) {
  const [tab, setTab] = useState<"password" | "sessions">("password")

  // Password state
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null)
  const [isChangingPassword, setIsChangingPassword] = useState(false)

  // Sessions state
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const [revokingId, setRevokingId] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && tab === "sessions") {
      loadSessions()
    }
  }, [isOpen, tab])

  async function loadSessions() {
    setIsLoadingSessions(true)
    try {
      const data = await authClient.getSessions()
      setSessions(data)
    } catch {
      showToast("Failed to load active sessions.")
    } finally {
      setIsLoadingSessions(false)
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault()
    setPasswordError(null)
    setPasswordSuccess(null)

    if (!currentPassword) {
      setPasswordError("Current password is required.")
      return
    }
    if (newPassword.length < 10) {
      setPasswordError("New password must be at least 10 characters.")
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.")
      return
    }

    setIsChangingPassword(true)
    try {
      await authClient.changePassword(currentPassword, newPassword)
      setPasswordSuccess("Password updated successfully. Other sessions have been revoked.")
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err: unknown) {
      if (err instanceof AuthError) {
        setPasswordError(err.message)
      } else {
        setPasswordError("Could not reach the server. Try again.")
      }
    } finally {
      setIsChangingPassword(false)
    }
  }

  async function handleRevokeSession(id: string) {
    setRevokingId(id)
    try {
      await authClient.revokeSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      showToast("Session revoked.")
    } catch {
      showToast("Failed to revoke session.")
    } finally {
      setRevokingId(null)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px] p-0 gap-0 border border-border bg-card rounded-[var(--radius)] shadow-none">
        <DialogHeader className="p-4 border-b border-border text-left">
          <DialogTitle className="text-sm font-semibold tracking-tight text-foreground font-mono">
            Account Security
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground font-mono mt-0.5">
            Manage your credentials and active data room sessions.
          </DialogDescription>
        </DialogHeader>

        {/* Tab Navigation */}
        <div className="flex border-b border-border bg-muted/30 px-4">
          <button
            type="button"
            onClick={() => {
              setTab("password")
              setPasswordError(null)
              setPasswordSuccess(null)
            }}
            className={`px-3 py-2 text-xs font-mono border-b-2 -mb-px transition-colors ${
              tab === "password"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Password
          </button>
          <button
            type="button"
            onClick={() => setTab("sessions")}
            className={`px-3 py-2 text-xs font-mono border-b-2 -mb-px transition-colors ${
              tab === "sessions"
                ? "border-primary text-foreground font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Active Sessions
          </button>
        </div>

        <div className="p-4">
          {tab === "password" ? (
            <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-3">
              {passwordError && (
                <div role="alert" className="p-2 border border-destructive/30 bg-destructive/10 text-xs text-destructive font-mono">
                  {passwordError}
                </div>
              )}
              {passwordSuccess && (
                <div role="status" className="p-2 border border-border bg-muted/40 text-xs text-foreground font-mono">
                  {passwordSuccess}
                </div>
              )}

              <AuthField
                id="curr-pwd"
                label="Current password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                required
              />

              <AuthField
                id="new-pwd"
                label="New password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                hint="At least 10 characters"
                autoComplete="new-password"
                required
              />

              <AuthField
                id="conf-pwd"
                label="Confirm new password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />

              <div className="mt-2 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onClose}
                  className="h-8 text-xs font-mono rounded-[var(--radius)]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isChangingPassword}
                  className="h-8 text-xs font-mono rounded-[var(--radius)]"
                >
                  {isChangingPassword && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                  Update password
                </Button>
              </div>
            </form>
          ) : (
            <div className="flex flex-col gap-2">
              {isLoadingSessions ? (
                <div className="flex items-center justify-center py-8 text-xs text-muted-foreground font-mono">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Loading sessions…
                </div>
              ) : sessions.length === 0 ? (
                <div className="py-6 text-center text-xs text-muted-foreground font-mono">
                  No active sessions found.
                </div>
              ) : (
                <div className="flex flex-col divide-y divide-border border border-border rounded-[var(--radius)]">
                  {sessions.map((sess) => (
                    <div key={sess.id} className="p-2.5 flex items-center justify-between text-xs font-mono">
                      <div className="flex items-start gap-2.5 min-w-0">
                        <Laptop className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-foreground truncate max-w-[200px]">
                              {sess.userAgent}
                            </span>
                            {sess.isCurrent && (
                              <span className="border border-primary/30 bg-primary/10 text-primary px-1 py-0.2 text-[10px]">
                                Current
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] text-muted-foreground">
                            IP: {sess.ip} · Active: {new Date(sess.lastSeenAt).toLocaleString()}
                          </span>
                        </div>
                      </div>

                      {!sess.isCurrent && (
                        <button
                          type="button"
                          onClick={() => handleRevokeSession(sess.id)}
                          disabled={revokingId === sess.id}
                          className="text-muted-foreground hover:text-destructive p-1 transition-colors"
                          title="Revoke session"
                        >
                          {revokingId === sess.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
