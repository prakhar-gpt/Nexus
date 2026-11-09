export interface User {
  id: string
  email: string
  name: string
  role: string
  createdAt?: string
  token?: string
}

export type Session = User

export interface SessionInfo {
  id: string
  createdAt: string
  lastSeenAt: string
  expiresAt: string
  userAgent: string
  ip: string
  isCurrent: boolean
}

export type AuthStatus = "loading" | "authenticated" | "unauthenticated"

