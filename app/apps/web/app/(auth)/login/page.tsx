import type { Metadata } from "next"
import { Suspense } from "react"
import { AuthForm } from "@/components/auth-form"

export const metadata: Metadata = {
  title: "Sign in · Nexus",
  description: "Sign in to Nexus Retail Data Room Copilot",
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <AuthForm mode="login" />
    </Suspense>
  )
}

