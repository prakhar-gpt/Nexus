"use client"

import React, { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { AuthField } from "@/components/auth/auth-field"
import { Button } from "@/components/ui/button"
import { AuthError } from "@/lib/auth/client"
import { useAuth } from "@/lib/auth/provider"

interface AuthFormProps {
  mode: "login" | "signup"
  embedded?: boolean
}

function isValidNext(path: string | null): boolean {
  return Boolean(path && path.startsWith("/") && !path.startsWith("//") && !path.includes("\\"))
}

export function AuthForm({ mode, embedded = false }: AuthFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextParam = searchParams.get("next")
  const targetRedirect = isValidNext(nextParam) ? nextParam! : "/rooms"

  const { signIn, signUp } = useAuth()
  const [activeMode, setActiveMode] = useState<"login" | "signup">(mode)

  useEffect(() => { setActiveMode(mode) }, [mode])

  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ [key: string]: string }>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (retryCountdown === null || retryCountdown <= 0) return
    const timer = setInterval(() => {
      setRetryCountdown((prev) => (prev === null || prev <= 1 ? (clearInterval(timer), null) : prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [retryCountdown])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setFieldErrors({})

    const errors: { [key: string]: string } = {}
    if (activeMode === "signup" && !name.trim()) errors.name = "Full name is required."
    if (!email.trim()) errors.email = "Email is required."
    else if (!email.includes("@")) errors.email = "Please enter a valid email address."
    if (!password) errors.password = "Password is required."
    else if (activeMode === "signup" && password.length < 10) errors.password = "Password must be at least 10 characters."

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    setIsSubmitting(true)
    try {
      if (activeMode === "login") await signIn(email.trim(), password)
      else await signUp(name.trim(), email.trim(), password)
      router.push(targetRedirect)
    } catch (err: any) {
      if (err instanceof AuthError) {
        if (err.status === 429) {
          const match = err.message.match(/(\d+)\s+seconds/i)
          setRetryCountdown(match ? parseInt(match[1], 10) : 60)
          setFormError("Too many attempts. Please wait before trying again.")
        } else {
          setFormError(err.message)
        }
      } else {
        setFormError("Could not reach the server. Try again.")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const formCard = (
    <div className={`w-full ${embedded ? "" : "max-w-[400px]"} flex flex-col gap-5 text-left font-mono`}>
      {embedded ? (
        <div className="flex border-b border-border text-xs">
          <button
            type="button"
            onClick={() => { setActiveMode("login"); setFormError(null); setFieldErrors({}) }}
            className={`flex-1 pb-2.5 text-center font-medium transition-colors border-b-2 -mb-[1px] cursor-pointer ${activeMode === "login" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => { setActiveMode("signup"); setFormError(null); setFieldErrors({}) }}
            className={`flex-1 pb-2.5 text-center font-medium transition-colors border-b-2 -mb-[1px] cursor-pointer ${activeMode === "signup" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
          >
            Create account
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1 border-b border-border pb-4">
          <h1 className="text-sm font-semibold tracking-tight text-foreground">
            {activeMode === "login" ? "Sign in to your account" : "Create your analyst account"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {activeMode === "login" ? "Access your deal rooms and analytical threads." : "Set up your workspace for commercial due diligence."}
          </p>
        </div>
      )}

      {formError && (
        <div role="alert" className="p-3 border border-destructive/40 bg-destructive/10 text-xs text-destructive leading-relaxed">
          {retryCountdown && retryCountdown > 0 ? `Too many attempts. Try again in ${retryCountdown} seconds.` : formError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {activeMode === "signup" && (
          <AuthField
            id="name"
            label="Full name"
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              if (fieldErrors.name) setFieldErrors((prev) => ({ ...prev, name: "" }))
            }}
            error={fieldErrors.name}
            autoComplete="name"
            placeholder="e.g. Jane Doe"
            disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
            autoFocus
          />
        )}

        <AuthField
          id="email"
          label="Work email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: "" }))
          }}
          error={fieldErrors.email}
          autoComplete="email"
          placeholder="analyst@firm.com"
          disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
          autoFocus={activeMode === "login"}
        />

        <AuthField
          id="password"
          label="Password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: "" }))
          }}
          error={fieldErrors.password}
          hint={activeMode === "signup" ? "At least 10 characters" : null}
          autoComplete={activeMode === "login" ? "current-password" : "new-password"}
          disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
        />

        <Button
          type="submit"
          disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
          className="w-full h-9 text-xs font-mono rounded-[var(--radius)] mt-2 cursor-pointer bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              {activeMode === "login" ? "Signing in…" : "Creating account…"}
            </>
          ) : activeMode === "login" ? (
            "Sign in"
          ) : (
            "Create account"
          )}
        </Button>
      </form>

      <div className="pt-2 border-t border-border flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {activeMode === "login" ? "Don't have an account?" : "Already have an account?"}
        </span>
        {embedded ? (
          <button
            type="button"
            onClick={() => {
              setActiveMode(activeMode === "login" ? "signup" : "login")
              setFormError(null)
              setFieldErrors({})
            }}
            className="text-foreground hover:text-primary transition-colors underline underline-offset-4 cursor-pointer"
          >
            {activeMode === "login" ? "Create account" : "Sign in"}
          </button>
        ) : (
          <Link
            href={activeMode === "login" ? `/signup${nextParam ? `?next=${encodeURIComponent(nextParam)}` : ""}` : `/login${nextParam ? `?next=${encodeURIComponent(nextParam)}` : ""}`}
            className="text-foreground hover:text-primary transition-colors underline underline-offset-4"
          >
            {activeMode === "login" ? "Create account" : "Sign in"}
          </Link>
        )}
      </div>
    </div>
  )

  if (embedded) return formCard

  return (
    <div className="flex min-h-screen flex-col justify-center py-12 px-6 sm:px-12 bg-background">
      <div className="w-full max-w-[400px] mx-auto flex flex-col gap-6 text-left">
        <div className="flex flex-col gap-1">
          <Link href="/" className="text-2xl font-bold tracking-tight text-foreground hover:text-primary transition-colors font-mono w-fit">
            <h1>Nexus</h1>
          </Link>
          <span className="text-[11px] text-muted-foreground font-mono">Retail Data Room Copilot</span>
        </div>
        {formCard}
      </div>
    </div>
  )
}
