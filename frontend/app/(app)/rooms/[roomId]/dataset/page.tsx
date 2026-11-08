"use client"

import React, { use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import { DataRoomContent } from "@/components/data-room-content"
import { useRoom } from "@/lib/room-context"

export default function FullPageDatasetFallback({
  params,
}: {
  params: Promise<{ roomId: string }>
}) {
  const unwrapped = use(params)
  const roomId = unwrapped.roomId

  const router = useRouter()
  const { room, mutateRoom } = useRoom()

  function handleClose() {
    router.push(`/rooms/${roomId}`)
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto p-6 bg-background">
      <div className="mx-auto w-full max-w-[720px] pb-12">
        <Link
          href={`/rooms/${roomId}`}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to conversation</span>
        </Link>

        <div className="pb-4 mb-4 border-b border-border">
          <h1 className="text-xl font-medium tracking-tight text-foreground">
            {room?.name ?? "Data Room"} dataset
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Manage spreadsheet ingestion, column mapping decisions, and quarantine audits.
          </p>
        </div>

        <DataRoomContent
          room={room}
          roomId={roomId}
          onClose={handleClose}
          onMutateRoom={mutateRoom}
        />
      </div>
    </div>
  )
}
