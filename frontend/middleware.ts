import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

function isValidRelativePath(path: string | null): boolean {
  if (!path) return false
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\")
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hasSession = request.cookies.has("nexus_session")

  // Protect /rooms and all subroutes
  if (pathname.startsWith("/rooms")) {
    if (!hasSession) {
      const fullPath = pathname + search
      const loginUrl = new URL("/login", request.url)
      loginUrl.searchParams.set("next", fullPath)
      return NextResponse.redirect(loginUrl)
    }
    return NextResponse.next()
  }

  // If already signed in, visiting /login or /signup redirects to rooms (or next if valid)
  if (pathname === "/login" || pathname === "/signup") {
    if (hasSession) {
      const nextParam = request.nextUrl.searchParams.get("next")
      const redirectPath = isValidRelativePath(nextParam) ? nextParam! : "/rooms"
      return NextResponse.redirect(new URL(redirectPath, request.url))
    }
    return NextResponse.next()
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/rooms/:path*", "/login", "/signup"],
}
