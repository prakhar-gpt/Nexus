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
}

function isValidNext(path: string | null): boolean {
  if (!path) return false
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\")
}

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextParam = searchParams.get("next")
  const targetRedirect = isValidNext(nextParam) ? nextParam! : "/rooms"

  const { signIn, signUp } = useAuth()

  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const [formError, setFormError] = useState<string | null>(null)
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ [key: string]: string }>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const nameInputRef = useRef<HTMLInputElement>(null)
  const emailInputRef = useRef<HTMLInputElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)

  // Countdown timer for 429 rate limit
  useEffect(() => {
    if (retryCountdown === null || retryCountdown <= 0) return
    const timer = setInterval(() => {
      setRetryCountdown((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer)
          return null
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [retryCountdown])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setFieldErrors({})

    const cleanEmail = email.trim()
    const cleanName = name.trim()
    const errors: { [key: string]: string } = {}

    if (!cleanEmail) {
      errors.email = "Email is required."
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      errors.email = "Please enter a valid work email."
    }

    if (!password) {
      errors.password = "Password is required."
    } else if (mode === "signup" && password.length < 10) {
      errors.password = "Password must be at least 10 characters."
    }

    if (mode === "signup" && !cleanName) {
      errors.name = "Full name is required."
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      if (errors.name) nameInputRef.current?.focus()
      else if (errors.email) emailInputRef.current?.focus()
      else if (errors.password) passwordInputRef.current?.focus()
      return
    }

    setIsSubmitting(true)
    try {
      if (mode === "login") {
        await signIn(cleanEmail, password)
      } else {
        await signUp(cleanEmail, password, cleanName)
      }
      router.push(targetRedirect)
    } catch (err: unknown) {
      if (err instanceof AuthError) {
        if (err.status === 429 && err.retryAfter) {
          setRetryCountdown(err.retryAfter)
          setFormError(`Too many attempts. Try again in ${err.retryAfter} seconds.`)
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

  return (
    <div className="flex min-h-screen flex-col justify-center py-12 px-6 sm:px-12 bg-background">
      <div className="w-full max-w-[400px] mx-auto flex flex-col gap-6 text-left">
        {/* Wordmark link to / */}
        <div className="flex flex-col gap-1">
          <Link
            href="/"
            className="text-3xl font-bold tracking-tight text-foreground hover:text-primary transition-colors font-mono w-fit"
          >
            <h1>
              Nexus
            </h1>
          </Link>
          <span className="text-[11px] text-muted-foreground font-mono">
            Retail Data Room Copilot
          </span>
        </div>

        {/* Page Title & Subtitle */}
        <div className="flex flex-col gap-1 border-b border-border pb-4">
          <h1 className="text-sm font-semibold tracking-tight text-foreground font-mono">
            {mode === "login" ? "Sign in to your account" : "Create your analyst account"}
          </h1>
          <p className="text-xs text-muted-foreground font-mono">
            {mode === "login"
              ? "Access your deal rooms and analytical threads."
              : "Set up your workspace for commercial due diligence."}
          </p>
        </div>

        {/* Form Error Alert */}
        {formError && (
          <div
            role="alert"
            className="p-3 border border-destructive/40 bg-destructive/10 text-xs text-destructive font-mono leading-relaxed"
          >
            {retryCountdown && retryCountdown > 0
              ? `Too many attempts. Try again in ${retryCountdown} seconds.`
              : formError}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "signup" && (
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
            autoFocus={mode === "login"}
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
            hint={mode === "signup" ? "At least 10 characters" : null}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
          />

          <Button
            type="submit"
            disabled={isSubmitting || Boolean(retryCountdown && retryCountdown > 0)}
            className="w-full h-9 text-xs font-mono rounded-[var(--radius)] mt-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                {mode === "login" ? "Signing in…" : "Creating account…"}
              </>
            ) : mode === "login" ? (
              "Sign in"
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        {/* Secondary Quiet Link */}
        <div className="pt-2 border-t border-border flex items-center justify-between text-xs font-mono">
          <span className="text-muted-foreground">
            {mode === "login" ? "Don't have an account?" : "Already have an account?"}
          </span>
          <Link
            href={
              mode === "login"
                ? `/signup${nextParam ? `?next=${encodeURIComponent(nextParam)}` : ""}`
                : `/login${nextParam ? `?next=${encodeURIComponent(nextParam)}` : ""}`
            }
            className="text-foreground hover:text-primary transition-colors underline underline-offset-4"
          >
            {mode === "login" ? "Create account" : "Sign in"}
          </Link>
        </div>
      </div>
    </div>
  )
}
