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

  // 1. Check if there are no uploads at all
  if (!latestUpload && (!room.health?.rows || room.health.rows === "0")) {
    return { type: "empty" }
  }

  // 2. Check rejected state
  if (latestUpload?.status === "rejected" || latestUpload?.status === "failed") {
    return {
      type: "rejected",
      reason:
        (latestUpload as any).reason ||
        "The uploaded spreadsheet did not meet data room schema requirements.",
    }
  }

  // 3. Check active ingestion state
  if (
    latestUpload &&
    ["uploading", "processing", "safety", "structure", "mapping", "load"].includes(
      latestUpload.status
    )
  ) {
    return {
      type: "ingesting",
      stage: latestUpload.status,
    }
  }

  // 4. Check if column mappings have uncertain items needing confirmation
  const mappings = room.mappings || []
  const uncertain = mappings.filter(
    (m) => m.needs_confirmation || (m.confidence < 0.7 && !m.confirmed_by_user)
  )

  if (uncertain.length > 0) {
    return {
      type: "needs_confirmation",
      count: uncertain.length,
      mappings: uncertain,
    }
  }

  // 5. Ready state (loaded with confirmed mappings or established data)
  if (
    latestUpload?.status === "loaded" ||
    (room.health?.rows && room.health.rows !== "0")
  ) {
    return { type: "ready" }
  }

  return { type: "empty" }
}

