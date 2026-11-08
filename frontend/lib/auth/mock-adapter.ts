import type { AuthAdapter, Session } from "./types"

// NOTE: This mock adapter simulates client-side credential storage and session persistence
// using localStorage and browser cookies. Real production security must be enforced by the API
// once dedicated backend authentication endpoints (/auth/signin, /auth/signup) are available.

const ACCOUNTS_KEY = "nexus_accounts"
const SESSION_KEY = "nexus_session"
const COOKIE_NAME = "nexus_session"

export const DEMO_USER: Session = {
  userId: "usr-demo-1",
  name: "Prakhar Gupta",
  email: "prakhar@nexus.ai",
  role: "Diligence Analyst",
}

async function hashPassword(password: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(password)
  const hashBuffer = await crypto.subtle.digest("SHA-256", data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("")
}

function setSessionCookie() {
  if (typeof document === "undefined") return
  // Store an opaque random token in the nexus_session cookie, not the session JSON
  const opaqueToken = crypto.randomUUID()
  // 7-day session cookie with SameSite=Lax for SSR and Next.js middleware protection
  document.cookie = `${COOKIE_NAME}=${opaqueToken}; path=/; max-age=604800; SameSite=Lax`
}

function clearSessionCookie() {
  if (typeof document === "undefined") return
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`
}

export class MockAuthAdapter implements AuthAdapter {
  private getAccounts(): Record<string, { name: string; email: string; passwordHash: string; userId: string }> {
    if (typeof window === "undefined") return {}
    try {
      const stored = localStorage.getItem(ACCOUNTS_KEY)
      return stored ? JSON.parse(stored) : {}
    } catch {
      return {}
    }
  }

  private saveAccounts(accounts: Record<string, { name: string; email: string; passwordHash: string; userId: string }>) {
    if (typeof window === "undefined") return
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts))
  }

  async signIn(email: string, password: string): Promise<Session> {
    const cleanEmail = email.trim().toLowerCase()
    const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true"

    // Only allow passwordless demo sign-in when NEXT_PUBLIC_DEMO_MODE === "true"
    if (cleanEmail === DEMO_USER.email && isDemoMode) {
      setSessionCookie()
      localStorage.setItem(SESSION_KEY, JSON.stringify(DEMO_USER))
      return DEMO_USER
    }

    const accounts = this.getAccounts()
    const account = accounts[cleanEmail]

    if (!account) {
      throw new Error("Email or password is incorrect.")
    }

    const hash = await hashPassword(password)
    if (account.passwordHash !== hash) {
      throw new Error("Email or password is incorrect.")
    }

    const session: Session = {
      userId: account.userId,
      name: account.name,
      email: account.email,
      role: "Diligence Analyst",
    }

    setSessionCookie()
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
    return session
  }

  async signUp(name: string, email: string, password: string): Promise<Session> {
    const cleanEmail = email.trim().toLowerCase()
    const cleanName = name.trim()

    const accounts = this.getAccounts()
    if (accounts[cleanEmail] || cleanEmail === DEMO_USER.email) {
      throw new Error("An account with this email already exists. Sign in instead.")
    }

    const passwordHash = await hashPassword(password)
    const userId = `usr-${Date.now().toString(36)}`

    accounts[cleanEmail] = {
      userId,
      name: cleanName,
      email: cleanEmail,
      passwordHash,
    }
    this.saveAccounts(accounts)

    const session: Session = {
      userId,
      name: cleanName,
      email: cleanEmail,
      role: "Diligence Analyst",
    }

    setSessionCookie()
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
    return session
  }

  async signOut(): Promise<void> {
    if (typeof window !== "undefined") {
      localStorage.removeItem(SESSION_KEY)
      clearSessionCookie()
    }
  }

  async getSession(): Promise<Session | null> {
    if (typeof window === "undefined") return null
    try {
      const stored = localStorage.getItem(SESSION_KEY)
      if (stored) {
        const session = JSON.parse(stored) as Session
        return session
      }
    } catch {
      // Fallback
    }
    return null
  }
}

export const defaultAuthAdapter = new MockAuthAdapter()
