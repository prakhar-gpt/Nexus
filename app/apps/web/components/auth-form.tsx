"use client"

import React, { useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Eye, EyeOff, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useSession } from "@/lib/auth/provider"
import { DEMO_USER } from "@/lib/auth/mock-adapter"

interface AuthFormProps {
  mode: "login" | "signup"
}

function isValidNext(path: string | null): boolean {
  if (!path) return false
  return path.startsWith("/") && !path.startsWith("//")
}

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextParam = searchParams.get("next")
  const targetRedirect = isValidNext(nextParam) ? nextParam! : "/rooms"

  const { signIn, signUp } = useSession()

  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true"

  function validateEmail(val: string): string | null {
    if (!val.trim()) return "Email is required."
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim())) {
      return "Please enter a valid work email."
    }
    return null
  }

  function validatePassword(val: string): string | null {
    if (!val) return "Password is required."
    if (mode === "signup" && val.length < 8) {
      return "Password must be at least 8 characters."
    }
    return null
  }

  function validateName(val: string): string | null {
    if (mode === "signup" && !val.trim()) {
      return "Full name is required."
    }
    return null
  }

  function handleBlur(field: "name" | "email" | "password") {
    let err: string | null = null
    if (field === "name") err = validateName(name)
    if (field === "email") err = validateEmail(email)
    if (field === "password") err = validatePassword(password)

    setFieldErrors((prev) => ({
      ...prev,
      [field]: err || "",
    }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    const nameErr = validateName(name)
    const emailErr = validateEmail(email)
    const passwordErr = validatePassword(password)

    if (nameErr || emailErr || passwordErr) {
      setFieldErrors({
        name: nameErr || "",
        email: emailErr || "",
        password: passwordErr || "",
      })
      return
    }

    setIsSubmitting(true)
    try {
      if (mode === "login") {
        await signIn(email, password)
      } else {
        await signUp(name, email, password)
      }
      router.replace(targetRedirect)
    } catch (err: any) {
      setFormError(err.message || "An unexpected error occurred. Please try again.")
      setIsSubmitting(false)
    }
  }

  async function handleDemoSignIn() {
    setIsSubmitting(true)
    setFormError(null)
    try {
      await signIn(DEMO_USER.email, "demo-password")
      router.replace(targetRedirect)
    } catch {
      setFormError("Could not log into demo account.")
      setIsSubmitting(false)
    }
  }

  const signupLink = nextParam ? `/signup?next=${encodeURIComponent(nextParam)}` : "/signup"
  const loginLink = nextParam ? `/login?next=${encodeURIComponent(nextParam)}` : "/login"

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background px-4 pb-12">
      <div className="w-full max-w-[360px] -mt-12 flex flex-col">
        {/* Top Header: Wordmark + Heading + Muted sentence */}
        <div className="flex flex-col gap-1 mb-8">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground select-none">
            Nexus
          </span>
          <h1 className="text-2xl font-medium tracking-tight text-foreground">
            {mode === "login" ? "Sign in" : "Create your account"}
          </h1>
          <p className="text-xs text-muted-foreground">
            Commercial due diligence and retail analytics.
          </p>
        </div>

        {/* Form-level error alert */}
        <div className="min-h-[28px] mb-3">
          {formError ? (
            <div
              role="alert"
              aria-live="assertive"
              className="flex items-center gap-2 p-2 text-xs text-destructive bg-destructive/10 border border-destructive/20"
            >
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{formError}</span>
            </div>
          ) : null}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Full Name for Signup */}
          {mode === "signup" && (
            <div className="flex flex-col gap-1">
              <label htmlFor="auth-name" className="text-xs font-medium text-foreground">
                Full name
              </label>
              <input
                id="auth-name"
                type="text"
                value={name}
                autoFocus
                autoComplete="name"
                disabled={isSubmitting}
                onChange={(e) => {
                  setName(e.target.value)
                  if (fieldErrors.name) setFieldErrors((p) => ({ ...p, name: "" }))
                }}
                onBlur={() => handleBlur("name")}
                placeholder="Alex Mercer"
                className={`h-9 w-full border bg-background px-3 text-base sm:text-xs text-foreground placeholder:text-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary ${
                  fieldErrors.name ? "border-destructive" : "border-input"
                }`}
              />
              <div className="min-h-[16px]">
                {fieldErrors.name ? (
                  <span className="text-[11px] text-destructive">{fieldErrors.name}</span>
                ) : null}
              </div>
            </div>
          )}

          {/* Email */}
          <div className="flex flex-col gap-1">
            <label htmlFor="auth-email" className="text-xs font-medium text-foreground">
              {mode === "signup" ? "Work email" : "Email"}
            </label>
            <input
              id="auth-email"
              type="email"
              value={email}
              autoFocus={mode === "login"}
              autoComplete="email"
              disabled={isSubmitting}
              onChange={(e) => {
                setEmail(e.target.value)
                if (fieldErrors.email) setFieldErrors((p) => ({ ...p, email: "" }))
              }}
              onBlur={() => handleBlur("email")}
              placeholder="analyst@firm.com"
              className={`h-9 w-full border bg-background px-3 text-base sm:text-xs text-foreground placeholder:text-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary ${
                fieldErrors.email ? "border-destructive" : "border-input"
              }`}
            />
            <div className="min-h-[16px]">
              {fieldErrors.email ? (
                <span className="text-[11px] text-destructive">{fieldErrors.email}</span>
              ) : null}
            </div>
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label htmlFor="auth-password" className="text-xs font-medium text-foreground">
              Password
            </label>
            <div className="relative flex items-center">
              <input
                id="auth-password"
                type={showPassword ? "text" : "password"}
                value={password}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                disabled={isSubmitting}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (fieldErrors.password) setFieldErrors((p) => ({ ...p, password: "" }))
                }}
                onBlur={() => handleBlur("password")}
                placeholder="••••••••"
                className={`h-9 w-full border bg-background px-3 pr-9 text-base sm:text-xs text-foreground placeholder:text-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary ${
                  fieldErrors.password ? "border-destructive" : "border-input"
                }`}
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((p) => !p)}
                className="absolute right-2.5 text-muted-foreground hover:text-foreground transition-colors"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <div className="min-h-[16px]">
              {fieldErrors.password ? (
                <span className="text-[11px] text-destructive">{fieldErrors.password}</span>
              ) : mode === "signup" ? (
                <span className="text-[11px] text-muted-foreground">At least 8 characters</span>
              ) : null}
            </div>
          </div>

          {/* Primary Action Button */}
          <Button
            type="submit"
            disabled={isSubmitting}
            className="h-9 w-full text-xs font-medium mt-1 cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                <span>{mode === "login" ? "Signing in…" : "Creating account…"}</span>
              </>
            ) : (
              <span>{mode === "login" ? "Sign in" : "Create account"}</span>
            )}
          </Button>
        </form>

        {/* Footer Navigation */}
        <div className="mt-6 flex flex-col items-center gap-3 text-xs text-muted-foreground">
          {mode === "login" ? (
            <Link href={signupLink} className="hover:text-foreground underline underline-offset-4">
              No account? Create one
            </Link>
          ) : (
            <Link href={loginLink} className="hover:text-foreground underline underline-offset-4">
              Already have an account? Sign in
            </Link>
          )}

          {mode === "login" && isDemoMode && (
            <button
              type="button"
              onClick={handleDemoSignIn}
              disabled={isSubmitting}
              className="mt-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
            >
              Use demo account
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

