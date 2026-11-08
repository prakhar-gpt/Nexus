import type { Metadata } from "next"
import { Suspense } from "react"
import { AuthForm } from "@/components/auth-form"

export const metadata: Metadata = {
  title: "Create account · Nexus",
  description: "Create your Nexus account for diligence analytics",
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <AuthForm mode="signup" />
    </Suspense>
  )
}

