"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
}

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { login, signup } = useAuth()
  const [activeTab, setActiveTab] = useState<"login" | "signup">("login")

  // Login fields
  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loginLoading, setLoginLoading] = useState(false)

  // Signup fields
  const [signupName, setSignupName] = useState("")
  const [signupEmail, setSignupEmail] = useState("")
  const [signupPassword, setSignupPassword] = useState("")
  const [signupError, setSignupError] = useState<string | null>(null)
  const [signupLoading, setSignupLoading] = useState(false)

  async function handleLoginSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoginError(null)

    if (!loginEmail.trim()) {
      setLoginError("Email is required.")
      return
    }
    if (!loginPassword) {
      setLoginError("Password is required.")
      return
    }

    setLoginLoading(true)
    try {
      // Simulate quick auth resolve
      await new Promise((r) => setTimeout(r, 400))
      login(loginEmail.trim())
      onClose()
    } catch {
      setLoginError("Invalid email or password.")
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleSignupSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSignupError(null)

    if (!signupName.trim()) {
      setSignupError("Full name is required.")
      return
    }
    if (!signupEmail.trim()) {
      setSignupError("Work email is required.")
      return
    }
    if (signupPassword.length < 6) {
      setSignupError("Password must be at least 6 characters.")
      return
    }

    setSignupLoading(true)
    try {
      await new Promise((r) => setTimeout(r, 400))
      signup(signupEmail.trim(), signupName.trim())
      onClose()
    } catch {
      setSignupError("Account creation failed. Try another email.")
    } finally {
      setSignupLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[400px] rounded-[var(--radius)] border border-border bg-popover p-6 shadow-none">
        <DialogHeader className="gap-1 p-0 text-left">
          <DialogTitle className="text-xl font-semibold text-foreground tracking-tight">
            Nexus
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Commercial due diligence & retail analytics
          </DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(val) => {
            setActiveTab(val as "login" | "signup")
            setLoginError(null)
            setSignupError(null)
          }}
          className="w-full mt-4"
        >
          <TabsList className="grid w-full grid-cols-2 bg-muted/60 p-1 border border-border">
            <TabsTrigger
              value="login"
              className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground"
            >
              Sign in
            </TabsTrigger>
            <TabsTrigger
              value="signup"
              className="text-xs data-[state=active]:bg-card data-[state=active]:text-foreground"
            >
              Create account
            </TabsTrigger>
          </TabsList>

          <TabsContent value="login" className="mt-4">
            <form onSubmit={handleLoginSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-foreground">
                  Email
                </label>
                <input
                  type="email"
                  value={loginEmail}
                  onChange={(e) => {
                    setLoginEmail(e.target.value)
                    setLoginError(null)
                  }}
                  placeholder="analyst@firm.com"
                  autoFocus
                  disabled={loginLoading}
                  className="h-8 border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-foreground">
                  Password
                </label>
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(e) => {
                    setLoginPassword(e.target.value)
                    setLoginError(null)
                  }}
                  placeholder="••••••••"
                  disabled={loginLoading}
                  className="h-8 border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              {loginError ? (
                <p role="alert" className="text-xs text-destructive">
                  {loginError}
                </p>
              ) : null}

              <div className="mt-2 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  disabled={loginLoading}
                  className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={loginLoading}
                  className="h-8 px-3 text-xs"
                >
                  {loginLoading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                      Signing in…
                    </>
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="signup" className="mt-4">
            <form onSubmit={handleSignupSubmit} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-foreground">
                  Full name
                </label>
                <input
                  type="text"
                  value={signupName}
                  onChange={(e) => {
                    setSignupName(e.target.value)
                    setSignupError(null)
                  }}
                  placeholder="Alex Mercer"
                  autoFocus
                  disabled={signupLoading}
                  className="h-8 border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-foreground">
                  Work email
                </label>
                <input
                  type="email"
                  value={signupEmail}
                  onChange={(e) => {
                    setSignupEmail(e.target.value)
                    setSignupError(null)
                  }}
                  placeholder="alex.mercer@firm.com"
                  disabled={signupLoading}
                  className="h-8 border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-foreground">
                  Password
                </label>
                <input
                  type="password"
                  value={signupPassword}
                  onChange={(e) => {
                    setSignupPassword(e.target.value)
                    setSignupError(null)
                  }}
                  placeholder="Minimum 6 characters"
                  disabled={signupLoading}
                  className="h-8 border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              {signupError ? (
                <p role="alert" className="text-xs text-destructive">
                  {signupError}
                </p>
              ) : null}

              <div className="mt-2 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  disabled={signupLoading}
                  className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={signupLoading}
                  className="h-8 px-3 text-xs"
                >
                  {signupLoading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                      Creating account…
                    </>
                  ) : (
                    "Create account"
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
