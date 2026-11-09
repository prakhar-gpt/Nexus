"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from "react"
import { authClient } from "./client"
import type { AuthStatus, User } from "./types"

interface AuthContextType {
  user: User | null
  session: User | null
  status: AuthStatus
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<User>
  signUp: (email: string, password: string, name: string) => Promise<User>
  signOut: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>("loading")

  const refreshUser = useCallback(async () => {
    try {
      const u = await authClient.me()
      setUser(u)
      setStatus("authenticated")
      if (typeof document !== "undefined") {
        document.cookie = "nexus_session=1; path=/; max-age=1209600; SameSite=Lax"
      }
    } catch {
      setUser(null)
      setStatus("unauthenticated")
      if (typeof document !== "undefined") {
        document.cookie = "nexus_session=; path=/; max-age=0; SameSite=Lax"
      }
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const u = await authClient.login(email, password)
      setUser(u)
      setStatus("authenticated")
      return u
    },
    []
  )

  const signUp = useCallback(
    async (email: string, password: string, name: string) => {
      const u = await authClient.signup(email, password, name)
      setUser(u)
      setStatus("authenticated")
      return u
    },
    []
  )

  const signOut = useCallback(async () => {
    try {
      await authClient.logout()
    } finally {
      setUser(null)
      setStatus("unauthenticated")
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        session: user,
        status,
        isLoading: status === "loading",
        signIn,
        signUp,
        signOut,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return ctx
}

// Backwards-compatible alias for existing components
export const useSession = useAuth
