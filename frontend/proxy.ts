import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

function isValidNextPath(path: string | null): boolean {
  if (!path) return false
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\")
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const sessionCookie = request.cookies.get("nexus_session")?.value
  const isAuthenticated = Boolean(sessionCookie)

  // 1. Auth routes (/login, /signup): redirect authenticated users to /rooms
  if (pathname === "/login" || pathname === "/signup") {
    if (isAuthenticated) {
      const nextParam = request.nextUrl.searchParams.get("next")
      const target = isValidNextPath(nextParam) ? nextParam! : "/rooms"
      return NextResponse.redirect(new URL(target, request.url))
    }
    return NextResponse.next()
  }

  // 2. Protected routes (/rooms, /rooms/*): redirect unauthenticated users to /login?next=...
  if (pathname.startsWith("/rooms")) {
    if (!isAuthenticated) {
      const nextUrl = new URL("/login", request.url)
      const currentPath = pathname + search
      if (isValidNextPath(currentPath)) {
        nextUrl.searchParams.set("next", currentPath)
      }
      return NextResponse.redirect(nextUrl)
    }
    return NextResponse.next()
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/login", "/signup", "/rooms/:path*"],
}
