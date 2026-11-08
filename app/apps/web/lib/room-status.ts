import type { Mapping, Room } from "./api"

export type RoomStatus =
  | { type: "empty" }
  | { type: "ingesting"; stage?: string }
  | { type: "needs_confirmation"; count: number; mappings: Mapping[] }
  | { type: "rejected"; reason: string }
  | { type: "ready" }

export function deriveRoomStatus(room?: Room | null): RoomStatus {
  if (!room) {
    return { type: "empty" }
  }

  const latestUpload = room.uploads && room.uploads.length > 0 ? room.uploads[0] : null
  const hasLoadedRows = Boolean(room.health?.rows && room.health.rows !== "0")

  // 1. If rows are loaded into the data room, it is ready for queries!
  if (hasLoadedRows) {
    return { type: "ready" }
  }

  // 2. Check if there are no uploads at all
  if (!latestUpload) {
    return { type: "empty" }
  }

  // 3. Check rejected state
  if (latestUpload.status === "rejected" || latestUpload.status === "failed") {
    return {
      type: "rejected",
      reason:
        (latestUpload as any).reason ||
        "The uploaded spreadsheet did not meet data room schema requirements.",
    }
  }

  // 4. Check active ingestion state
  if (
    ["uploading", "processing", "safety", "structure", "mapping", "load", "loading", "received"].includes(
      latestUpload.status
    )
  ) {
    return {
      type: "ingesting",
      stage: latestUpload.status,
    }
  }

  // 5. Check if canonical column mappings require user confirmation
  const mappings = room.mappings || []
  const uncertain = mappings.filter(
    (m) => m.canonical && m.needs_confirmation && !m.confirmed_by_user
  )

  if (uncertain.length > 0) {
    return {
      type: "needs_confirmation",
      count: uncertain.length,
      mappings: uncertain,
    }
  }

  // 6. Ready state
  if (latestUpload.status === "loaded" || latestUpload.status === "accepted") {
    return { type: "ready" }
  }

  return { type: "empty" }
}
