"use client"

import React, { useState } from "react"
import { Check, Download, ArrowRight, ChevronDown, ChevronUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dropzone } from "@/components/dropzone"
import { PipelineStepper } from "@/components/pipeline-stepper"
import { MappingTable } from "@/components/mapping-table"
import { API_URL, apiFetch, type Mapping, type Room } from "@/lib/api"
import { deriveRoomStatus } from "@/lib/room-status"

interface DataRoomContentProps {
  room: Room | null
  roomId: string | number
  onClose?: () => void
  onMutateRoom?: () => Promise<any>
}

export function DataRoomContent({
  room,
  roomId,
  onClose,
  onMutateRoom,
}: DataRoomContentProps) {
  const latestUpload = room?.uploads && room.uploads.length > 0 ? room.uploads[0] : null

  const [liveName, setLiveName] = useState<string | null>(latestUpload?.original_name ?? null)
  const [liveStatus, setLiveStatus] = useState<string | null>(latestUpload?.status ?? null)
  const [liveReason, setLiveReason] = useState<string | null>(null)
  const [liveStages, setLiveStages] = useState<{ stage: string; status: string; reason?: string }[]>([])
  const [liveMappings, setLiveMappings] = useState<Mapping[] | null>(room?.mappings ?? null)
  const [liveUploadId, setLiveUploadId] = useState<string | null>(latestUpload?.id ?? null)
  const [confirming, setConfirming] = useState(false)
  const [showAllQuarantine, setShowAllQuarantine] = useState(false)

  const mappings = liveMappings || room?.mappings || []
  const currentStatus = deriveRoomStatus({
    ...room,
    uploads: liveUploadId ? [{ id: liveUploadId, original_name: liveName || "", status: liveStatus || "uploading" }] : room?.uploads || [],
    mappings,
  } as any)

  const isUploading = liveStatus === "uploading" || (liveStages.length > 0 && liveStatus !== "loaded" && liveStatus !== "rejected")

  async function handleFile(file: File) {
    setLiveName(file.name)
    setLiveStatus("uploading")
    setLiveReason(null)
    setLiveStages([
      { stage: "safety", status: "done" },
      { stage: "structure", status: "active" },
    ])
    setLiveMappings(null)
    setLiveUploadId(null)

    const form = new FormData()
    form.append("file", file)
    try {
      const res = await apiFetch(`${API_URL}/workspaces/${roomId}/uploads`, {
        method: "POST",
        body: form,
      })
      if (!res.ok) {
        setLiveStatus("rejected")
        setLiveReason("The file was rejected by the server.")
        return
      }
      const body = (await res.json()) as { upload_id: number; status: string }
      setLiveUploadId(String(body.upload_id))
      setLiveStatus(body.status)
      listenToUpload(body.upload_id)
    } catch {
      setLiveStatus("rejected")
      setLiveReason("Couldn't reach the server. Check your connection and try again.")
      setLiveStages((curr) =>
        curr.map((st) =>
          st.status === "active"
            ? { ...st, status: "failed", reason: "Connection failed" }
            : st
        )
      )
    }
  }

  function listenToUpload(uploadId: number) {
    const source = new EventSource(`${API_URL}/uploads/${uploadId}/events`)
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.stage && payload.status) {
          setLiveStages((curr) => [
            ...curr.filter((item) => item.stage !== payload.stage),
            { stage: payload.stage, status: payload.status, reason: payload.reason },
          ])
        }
        if (payload.reason) setLiveReason(payload.reason)
        if (payload.final) {
          setLiveStatus(payload.final)
          source.close()
          loadMappings(uploadId)
          onMutateRoom?.()
        }
      } catch {}
    }
    source.onerror = () => {
      source.close()
      setLiveStages((curr) =>
        curr.map((st) =>
          st.status === "active"
            ? { ...st, status: "failed", reason: "Lost connection to the upload. Reload to check status." }
            : st
        )
      )
      setLiveReason("Lost connection to the upload. Reload to check status.")
      onMutateRoom?.()
    }
  }

  async function loadMappings(uploadId: number) {
    try {
      const res = await apiFetch(`${API_URL}/uploads/${uploadId}/mapping`)
      if (!res.ok) return
      const body = (await res.json()) as { mappings: Mapping[] }
      setLiveMappings(body.mappings)
    } catch {}
  }

  async function handleConfirmMapping(decisions: Record<string, string>): Promise<boolean> {
    const id = liveUploadId ?? latestUpload?.id
    if (!id) return true
    setConfirming(true)
    try {
      const res = await apiFetch(`${API_URL}/uploads/${id}/mapping`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      })
      if (!res.ok) throw new Error("Could not save mapping.")
      setLiveMappings((prev) =>
        prev
          ? prev.map((m) =>
              decisions[m.source]
                ? {
                    ...m,
                    canonical: decisions[m.source],
                    needs_confirmation: false,
                    confirmed_by_user: true,
                  }
                : m
            )
          : null
      )
      await onMutateRoom?.()
      return true
    } catch {
      return false
    } finally {
      setConfirming(false)
    }
  }

  const quarantine = room?.quarantine || []
  const displayedQuarantine = showAllQuarantine ? quarantine : quarantine.slice(0, 10)
  const isReady = currentStatus.type === "ready"

  return (
    <div className="flex flex-col divide-y divide-border text-xs">
      {/* Ready Success Banner with "Start asking" button (Flow 3) */}
      {isReady && (
        <div className="py-3 px-1 flex items-center justify-between bg-ok/5 border border-ok/20 text-ok mb-2">
          <div className="flex items-center gap-1.5 font-medium">
            <Check className="h-4 w-4 stroke-[2.5]" />
            <span>Dataset loaded and column mappings confirmed</span>
          </div>
          {onClose && (
            <Button size="sm" onClick={onClose} className="h-7 px-3 text-xs font-medium">
              <span>Start asking</span>
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
      )}

      {/* Section 1: Summary */}
      <div className="py-4">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-2">
          Dataset summary
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="border border-border/60 bg-muted/20 p-2.5">
            <span className="text-[11px] text-muted-foreground block">Rows loaded</span>
            <span className="font-mono text-sm font-medium tabular-nums text-foreground">
              {room?.health?.rows ? Number(room.health.rows).toLocaleString() : "0"} rows
            </span>
          </div>
          <div className="border border-border/60 bg-muted/20 p-2.5">
            <span className="text-[11px] text-muted-foreground block">Date range</span>
            <span className="font-mono text-xs font-medium tabular-nums text-foreground truncate block">
              {room?.health?.first_order && room.health.last_order
                ? `${room.health.first_order} to ${room.health.last_order}`
                : "None"}
            </span>
          </div>
          <div className="border border-border/60 bg-muted/20 p-2.5">
            <span className="text-[11px] text-muted-foreground block">Last upload</span>
            <span className="font-mono text-xs font-medium text-foreground truncate block">
              {liveName ?? "No file"}
            </span>
          </div>
        </div>
      </div>

      {/* Section 2: Dropzone */}
      <div className="py-4">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-2">
          Upload spreadsheet
        </span>
        <Dropzone
          onFileSelect={handleFile}
          disabled={isUploading}
          currentFileName={liveName}
          errorReason={liveReason}
        />
      </div>

      {/* Section 3: Pipeline stepper */}
      {(liveStages.length > 0 || liveStatus) && (
        <div className="py-4">
          <PipelineStepper
            stages={liveStages}
            overallStatus={liveStatus}
            overallReason={liveReason}
          />
        </div>
      )}

      {/* Section 4: Column mapping */}
      {mappings.length > 0 && (
        <div className="py-4">
          <MappingTable
            mappings={mappings}
            confirming={confirming}
            onConfirm={handleConfirmMapping}
          />
        </div>
      )}

      {/* Section 5: Quarantine */}
      {quarantine.length > 0 && (
        <div className="py-4 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Quarantine ({quarantine.length}{" "}
              {quarantine.length === 1 ? "row set aside" : "rows set aside"})
            </span>
            {liveUploadId && (
              <a
                href={`${API_URL}/uploads/${liveUploadId}/health?download=quarantine`}
                className="inline-flex items-center gap-1 text-[11px] text-foreground hover:underline"
              >
                <Download className="h-3 w-3" />
                <span>Download report CSV</span>
              </a>
            )}
          </div>

          <div className="overflow-x-auto border border-border">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/40 font-mono text-[11px] text-muted-foreground">
                  <th className="py-1.5 px-3 w-20">Row</th>
                  <th className="py-1.5 px-3">Reason</th>
                  <th className="py-1.5 px-3">Raw value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {displayedQuarantine.map((q, idx) => (
                  <tr key={idx} className="hover:bg-muted/20">
                    <td className="py-1.5 px-3 font-mono tabular-nums text-muted-foreground">
                      {q.row_number}
                    </td>
                    <td className="py-1.5 px-3 text-destructive">{q.reason}</td>
                    <td className="py-1.5 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-xs">
                      {q.raw_value ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Expander: Show all N rows */}
          {quarantine.length > 10 && (
            <button
              type="button"
              onClick={() => setShowAllQuarantine((prev) => !prev)}
              className="self-start text-xs text-muted-foreground hover:text-foreground font-medium underline underline-offset-2 transition-colors pt-1"
            >
              {showAllQuarantine
                ? "Show fewer"
                : `Show all ${quarantine.length}`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
