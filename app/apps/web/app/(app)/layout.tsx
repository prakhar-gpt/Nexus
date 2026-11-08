"use client"

import React, { useEffect, Suspense } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useSession } from "@/lib/auth/provider"
import { ChatStoreProvider } from "@/lib/chat-store"

function isValidNext(path: string | null): boolean {
  if (!path) return false
  return path.startsWith("/") && !path.startsWith("//")
}

function AuthGuardInner({ children }: { children: React.ReactNode }) {
  const { session, isLoading } = useSession()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (!isLoading && !session) {
      const fullPath = pathname + (searchParams.toString() ? `?${searchParams.toString()}` : "")
      const nextTarget = isValidNext(fullPath) ? fullPath : "/rooms"
      router.replace(`/login?next=${encodeURIComponent(nextTarget)}`)
    }
  }, [session, isLoading, router, pathname, searchParams])

  // Layer 2 guard: render full-height skeleton while checking session to avoid any flash of protected content
  if (isLoading || !session) {
    return (
      <div className="flex h-screen w-full flex-col bg-background animate-pulse">
        <header className="h-14 border-b border-border px-6 flex items-center justify-between">
          <div className="h-4 w-28 bg-muted" />
          <div className="h-8 w-24 bg-muted" />
        </header>
        <main className="max-w-[960px] mx-auto w-full px-6 py-10 flex flex-col gap-6 flex-1">
          <div className="h-8 w-44 bg-muted" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div className="h-40 bg-muted/40 border border-border" />
            <div className="h-40 bg-muted/40 border border-border" />
            <div className="h-40 bg-muted/40 border border-border" />
          </div>
        </main>
      </div>
    )
  }

  return <ChatStoreProvider>{children}</ChatStoreProvider>
}

export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-full flex-col bg-background animate-pulse">
          <header className="h-14 border-b border-border px-6 flex items-center justify-between">
            <div className="h-4 w-28 bg-muted" />
            <div className="h-8 w-24 bg-muted" />
          </header>
        </div>
      }
    >
      <AuthGuardInner>{children}</AuthGuardInner>
    </Suspense>
  )
}
