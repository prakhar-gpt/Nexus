"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface CreateWorkspaceModalProps {
  isOpen: boolean
  onClose: () => void
  onCreate: (name: string) => Promise<boolean | void>
}

export function CreateWorkspaceModal({
  isOpen,
  onClose,
  onCreate,
}: CreateWorkspaceModalProps) {
  const [name, setName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return

    setSubmitting(true)
    setError(null)
    try {
      const result = await onCreate(trimmed)
      if (result === false) {
        setError("Could not create data room. Try again.")
      } else {
        setName("")
        onClose()
      }
    } catch (err: any) {
      setError(err?.message || "Could not create data room.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[420px] rounded-[var(--radius)] border border-border bg-popover p-6 shadow-none">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="gap-1 p-0 text-left">
            <DialogTitle className="text-base font-medium text-foreground">
              New data room
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Isolated workspace for querying sales data, inspecting SQL, and auditing metrics.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <label
              htmlFor="room-name-input"
              className="text-xs font-medium text-foreground block mb-1.5"
            >
              Name
            </label>
            <input
              id="room-name-input"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError(null)
              }}
              placeholder="e.g. Project Apollo diligence"
              autoFocus
              disabled={submitting}
              className="h-8 w-full border border-input bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            {error ? (
              <p role="alert" className="mt-1.5 text-xs text-destructive">
                {error}
              </p>
            ) : null}
          </div>

          <DialogFooter className="flex-row justify-end gap-2 border-0 bg-transparent p-0">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={submitting}
              className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!name.trim() || submitting}
              className="h-8 px-3 text-xs font-medium"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  Creating…
                </>
              ) : (
                "Create"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
