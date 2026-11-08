"use client"

import { useState } from "react"
import { Database, Plus } from "lucide-react"
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
  onCreate: (name: string) => void
}

export function CreateWorkspaceModal({
  isOpen,
  onClose,
  onCreate,
}: CreateWorkspaceModalProps) {
  const [name, setName] = useState("")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (name.trim()) {
      onCreate(name.trim())
      setName("")
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[420px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-primary/10 text-primary">
                <Database className="h-4 w-4" />
              </div>
              <DialogTitle className="text-base font-semibold">New Data Room</DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Create an isolated workspace to upload diligence datasets and run audits.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <label className="text-xs font-medium text-foreground block mb-1.5">
              Data Room Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Project Apollo Diligence"
              autoFocus
              required
              className="h-8 w-full rounded border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-xs h-8"
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" className="text-xs h-8">
              <Plus className="h-3.5 w-3.5 mr-1" />
              Create Room
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

