"use client"

import React, { useState } from "react"
import { Eye, EyeOff } from "lucide-react"

interface AuthFieldProps {
  id: string
  label: string
  type?: "text" | "email" | "password"
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  error?: string | null
  hint?: string | null
  autoComplete?: string
  placeholder?: string
  required?: boolean
  disabled?: boolean
  autoFocus?: boolean
}

export function AuthField({
  id,
  label,
  type = "text",
  value,
  onChange,
  error,
  hint,
  autoComplete,
  placeholder,
  required,
  disabled,
  autoFocus,
}: AuthFieldProps) {
  const [showPassword, setShowPassword] = useState(false)
  const isPassword = type === "password"
  const actualType = isPassword ? (showPassword ? "text" : "password") : type

  const errorId = `${id}-error`
  const hintId = `${id}-hint`

  return (
    <div className="flex flex-col gap-1.5 text-left">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-xs font-medium text-foreground tracking-tight">
          {label}
        </label>
        {hint && !error && (
          <span id={hintId} className="text-[11px] text-muted-foreground font-mono">
            {hint}
          </span>
        )}
      </div>

      <div className="relative">
        <input
          id={id}
          type={actualType}
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          autoFocus={autoFocus}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : hint ? hintId : undefined}
          className={`flex h-9 w-full rounded-[var(--radius)] border bg-background px-3 py-1 text-xs text-foreground font-mono transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? "border-destructive text-destructive" : "border-border"
          } ${isPassword ? "pr-9" : ""}`}
        />

        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-0.5"
          >
            {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      {error && (
        <span id={errorId} role="alert" className="text-[11px] text-destructive font-mono">
          {error}
        </span>
      )}
    </div>
  )
}
