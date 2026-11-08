"use client"

import { useEffect } from "react"
import { AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log error internally without exposing raw stack trace to user
    console.error("App Error:", error)
  }, [error])

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background px-4 text-center">
      <div className="flex h-10 w-10 items-center justify-center bg-destructive/10 text-destructive mb-3 border border-destructive/20">
        <AlertCircle className="h-5 w-5" />
      </div>
      <h1 className="text-lg font-medium text-foreground tracking-tight">
        Something went wrong
      </h1>
      <p className="mt-1 text-xs text-muted-foreground max-w-sm mb-6">
        Could not connect to the data room service or load the requested resource.
      </p>
      <Button size="sm" onClick={() => reset()} className="h-8 text-xs font-medium">
        <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
        <span>Try again</span>
      </Button>
    </div>
  )
}

