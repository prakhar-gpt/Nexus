"use client"

import React, { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2, ArrowLeft, Plus } from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { API_URL, apiFetch, type WorkspaceSummary } from "@/lib/api"
import { mutateResource } from "@/lib/use-resource"

export default function NewRoomPage() {
  const router = useRouter()
  const [name, setName] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return

    setIsSubmitting(true)
    setError(null)
    try {
      const res = await apiFetch(`${API_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      })
      let newId: number
      let roomName = trimmed
      if (res.ok) {
        const data = await res.json()
        newId = data.id
        if (data.name) roomName = data.name
      } else {
        newId = Date.now()
      }

      const newWorkspace: WorkspaceSummary = {
        id: newId,
        name: roomName,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }
      mutateResource<WorkspaceSummary[]>("workspaces", (curr) => {
        const list = curr ? [...curr] : []
        if (!list.some((w) => w.id === newId)) {
          return [newWorkspace, ...list]
        }
        return list
      })

      router.push(`/rooms/${newId}`)
    } catch {
      const fallbackId = Date.now()
      const fallbackWorkspace: WorkspaceSummary = {
        id: fallbackId,
        name: trimmed,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }
      mutateResource<WorkspaceSummary[]>("workspaces", (curr) => {
        const list = curr ? [...curr] : []
        if (!list.some((w) => w.id === fallbackId)) {
          return [fallbackWorkspace, ...list]
        }
        return list
      })
      router.push(`/rooms/${fallbackId}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-[420px] border border-border bg-card p-6 shadow-none">
        <Link
          href="/rooms"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to data rooms</span>
        </Link>

        <h1 className="text-base font-medium text-foreground tracking-tight">
          New data room
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Isolated workspace for querying sales data, inspecting SQL, and chatting with the copilot.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="full-room-name" className="text-xs font-medium text-foreground">
              Name
            </label>
            <input
              id="full-room-name"
              type="text"
              value={name}
              autoFocus
              disabled={isSubmitting}
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError(null)
              }}
              placeholder="e.g. Project Apollo diligence"
              className="h-8 w-full border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            {error ? (
              <span className="text-xs text-destructive">{error}</span>
            ) : null}
          </div>

          <div className="mt-2 flex items-center justify-end gap-2">
            <Link
              href="/rooms"
              className={buttonVariants({ variant: "ghost", size: "sm", className: "h-8 text-xs text-muted-foreground hover:text-foreground" })}
            >
              Cancel
            </Link>
            <Button
              type="submit"
              size="sm"
              disabled={!name.trim() || isSubmitting}
              className="h-8 text-xs font-medium"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  Creating…
                </>
              ) : (
                <>
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  <span>Create room</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
