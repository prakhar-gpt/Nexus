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
  const { user, session, isLoading } = useSession()
  const currentUser = user || session
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (!isLoading && !currentUser) {
      const fullPath = pathname + (searchParams.toString() ? `?${searchParams.toString()}` : "")
      const nextTarget = isValidNext(fullPath) ? fullPath : "/rooms"
      router.replace(`/login?next=${encodeURIComponent(nextTarget)}`)
    }
  }, [currentUser, isLoading, router, pathname, searchParams])

  // Layer 2 guard: render full-height skeleton while checking session to avoid any flash of protected content
  if (isLoading || !currentUser) {
    return (
      <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden animate-pulse">
        <aside className="hidden md:block h-full w-[260px] border-r border-sidebar-border bg-sidebar p-3 shrink-0">
          <div className="h-4 w-20 bg-muted mb-4" />
          <div className="h-8 w-full bg-muted mb-6" />
          <div className="space-y-2">
            <div className="h-8 w-full bg-muted/60" />
            <div className="h-8 w-full bg-muted/40" />
            <div className="h-8 w-full bg-muted/30" />
          </div>
        </aside>
        <main className="flex-1 flex flex-col justify-between pt-16 sm:pt-20 pb-4 max-w-[720px] mx-auto w-full px-4 sm:px-6">
          <div className="space-y-3">
            <div className="h-8 w-44 bg-muted" />
            <div className="h-4 w-72 bg-muted/60" />
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
        <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden animate-pulse">
          <aside className="hidden md:block h-full w-[260px] border-r border-sidebar-border bg-sidebar p-3 shrink-0">
            <div className="h-4 w-20 bg-muted mb-4" />
            <div className="h-8 w-full bg-muted mb-6" />
          </aside>
          <main className="flex-1 max-w-[720px] mx-auto w-full px-4 sm:px-6 pt-16 sm:pt-20">
            <div className="h-8 w-44 bg-muted" />
          </main>
        </div>
      }
    >
      <AuthGuardInner>{children}</AuthGuardInner>
    </Suspense>
  )
}
