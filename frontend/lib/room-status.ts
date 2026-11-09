import type { Mapping, Room } from "./api"

export type RoomStatus =
  | { type: "empty" }
  | { type: "ingesting"; stage?: string }
  | { type: "rejected"; reason: string }
  | { type: "ready" }

export function deriveRoomStatus(room?: Room | null): RoomStatus {
  if (!room) {
    return { type: "empty" }
  }

  const latestUpload = room.uploads && room.uploads.length > 0 ? room.uploads[0] : null
  const hasLoadedRows = Boolean(room.health?.rows && room.health.rows !== "0")
  const hasApprovedDatasets = Boolean(room.datasets && room.datasets.length > 0)

  // 1. If rows or approved datasets are in the data room, it is ready for queries!
  if (hasLoadedRows || hasApprovedDatasets) {
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

  // 6. Ready state
  if (latestUpload.status === "loaded" || latestUpload.status === "accepted") {
    return { type: "ready" }
  }

  return { type: "empty" }
}
