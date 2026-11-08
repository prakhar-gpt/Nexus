"use client"

import { createContext, useContext, useEffect, useState } from "react"

export type User = {
  id: string
  name: string
  email: string
  role: string
}

const DEFAULT_USER: User = {
  id: "user-1",
  name: "Prakhar Gupta",
  email: "prakhar@nexus.ai",
  role: "Consulting Analyst",
}

interface AuthContextType {
  user: User | null
  login: (email: string, name?: string) => void
  signup: (email: string, name: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType>({
  user: DEFAULT_USER,
  login: () => {},
  signup: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("nexus_user")
      if (stored) {
        try {
          return JSON.parse(stored)
        } catch {
          return DEFAULT_USER
        }
      }
    }
    return DEFAULT_USER
  })

  function login(email: string, name?: string) {
    const formattedName = name?.trim() || email.split("@")[0].replace(".", " ")
    const newUser: User = {
      id: `user-${Date.now().toString(36)}`,
      name: formattedName.charAt(0).toUpperCase() + formattedName.slice(1),
      email: email.trim().toLowerCase(),
      role: "Diligence Analyst",
    }
    setUser(newUser)
    localStorage.setItem("nexus_user", JSON.stringify(newUser))
  }

  function signup(email: string, name: string) {
    login(email, name)
  }

  function logout() {
    setUser(null)
    localStorage.removeItem("nexus_user")
  }

  return (
    <AuthContext.Provider value={{ user, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
