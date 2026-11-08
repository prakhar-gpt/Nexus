"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from "react"
import type { Session, AuthAdapter } from "./types"
import { defaultAuthAdapter } from "./mock-adapter"

interface AuthContextType {
  session: Session | null
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<Session>
  signUp: (name: string, email: string, password: string) => Promise<Session>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({
  children,
  adapter = defaultAuthAdapter,
}: {
  children: React.ReactNode
  adapter?: AuthAdapter
}) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    adapter
      .getSession()
      .then((s) => {
        if (mounted) {
          setSession(s)
          setIsLoading(false)
        }
      })
      .catch(() => {
        if (mounted) setIsLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [adapter])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const s = await adapter.signIn(email, password)
      setSession(s)
      return s
    },
    [adapter]
  )

  const signUp = useCallback(
    async (name: string, email: string, password: string) => {
      const s = await adapter.signUp(name, email, password)
      setSession(s)
      return s
    },
    [adapter]
  )

  const signOut = useCallback(async () => {
    await adapter.signOut()
    setSession(null)
  }, [adapter])

  return (
    <AuthContext.Provider value={{ session, isLoading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useSession must be used within an AuthProvider")
  }
  return ctx
}

