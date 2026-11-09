"use client"

import React from "react"
import Link from "next/link"
import { useSession } from "@/lib/auth/provider"

export function LandingSessionButton() {
  const { user, session } = useSession()
  const isAuthenticated = Boolean(user || session)

  if (isAuthenticated) {
    return (
      <Link
        href="/rooms"
        className="bg-primary text-primary-foreground hover:bg-primary/90 px-3.5 py-1.5 text-xs font-medium transition-colors"
      >
        Open Nexus
      </Link>
    )
  }

  return null
}
