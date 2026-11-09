import { API_URL, apiFetch } from "@/lib/api"
import type { SessionInfo, User } from "./types"

export class AuthError extends Error {
  status: number
  retryAfter?: number

  constructor(message: string, status: number, retryAfter?: number) {
    super(message)
    this.name = "AuthError"
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function handleAuthResponse<T>(res: Response): Promise<T> {
  if (res.status === 429) {
    const retryHeader = res.headers.get("Retry-After")
    const retrySecs = retryHeader ? parseInt(retryHeader, 10) : 60
    let detail = `Too many attempts. Try again in ${retrySecs} seconds.`
    try {
      const data = await res.json()
      if (data?.detail) detail = data.detail
    } catch {}
    throw new AuthError(detail, 429, retrySecs)
  }

  if (!res.ok) {
    let detail = "Could not reach the server. Try again."
    try {
      const data = await res.json()
      if (data?.detail) {
        if (typeof data.detail === "string") {
          detail = data.detail
        } else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
          detail = data.detail[0].msg
        }
      }
    } catch {}
    throw new AuthError(detail, res.status)
  }

  return res.json()
}

export const authClient = {
  async login(email: string, password: string): Promise<User> {
    const res = await apiFetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
    })
    const user = await handleAuthResponse<User>(res)
    if (typeof document !== "undefined") {
      document.cookie = "nexus_session=1; path=/; max-age=1209600; SameSite=Lax"
    }
    return user
  },

  async signup(email: string, password: string, name: string): Promise<User> {
    const res = await apiFetch(`${API_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
        name: name.trim(),
      }),
    })
    const user = await handleAuthResponse<User>(res)
    if (typeof document !== "undefined") {
      document.cookie = "nexus_session=1; path=/; max-age=1209600; SameSite=Lax"
    }
    return user
  },

  async logout(): Promise<void> {
    try {
      await apiFetch(`${API_URL}/auth/logout`, {
        method: "POST",
      })
    } finally {
      if (typeof document !== "undefined") {
        document.cookie = "nexus_session=; path=/; max-age=0; SameSite=Lax"
      }
    }
  },

  async me(): Promise<User> {
    const res = await apiFetch(`${API_URL}/auth/me`, {
      method: "GET",
      cache: "no-store",
    })
    return handleAuthResponse<User>(res)
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<{ ok: boolean }> {
    const res = await apiFetch(`${API_URL}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    })
    return handleAuthResponse<{ ok: boolean }>(res)
  },

  async getSessions(): Promise<SessionInfo[]> {
    const res = await apiFetch(`${API_URL}/auth/sessions`, {
      method: "GET",
      cache: "no-store",
    })
    return handleAuthResponse<SessionInfo[]>(res)
  },

  async revokeSession(sessionId: string): Promise<{ ok: boolean }> {
    const res = await apiFetch(`${API_URL}/auth/sessions/${sessionId}`, {
      method: "DELETE",
    })
    return handleAuthResponse<{ ok: boolean }>(res)
  },
}
