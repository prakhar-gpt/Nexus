"use client"

import React, { use } from "react"
import { useRouter } from "next/navigation"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DataRoomContent } from "@/components/data-room-content"
import { useRoom } from "@/lib/room-context"

export default function InterceptedDatasetModal({
  params,
}: {
  params: Promise<{ roomId: string }>
}) {
  const unwrapped = use(params)
  const roomId = unwrapped.roomId

  const router = useRouter()
  const { room, mutateRoom } = useRoom()

  function handleClose() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back()
    } else {
      router.replace(`/rooms/${roomId}`)
    }
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-w-[720px] max-h-[85vh] overflow-y-auto rounded-[var(--radius)] border border-border bg-popover p-6 shadow-none">
        <DialogHeader className="gap-1 p-0 text-left pb-4 border-b border-border">
          <DialogTitle className="text-base font-medium text-foreground">
            {room?.name ?? "Data Room"} dataset
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Manage spreadsheet ingestion, column mapping decisions, and quarantine audits.
          </DialogDescription>
        </DialogHeader>

        <DataRoomContent
          room={room}
          roomId={roomId}
          onClose={handleClose}
          onMutateRoom={mutateRoom}
        />
      </DialogContent>
    </Dialog>
  )
}
