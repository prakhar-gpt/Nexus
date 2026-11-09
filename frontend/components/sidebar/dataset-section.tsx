"use client"

import React, { useState } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Plus, MoreHorizontal, Download, Trash2, Edit2, Loader2 } from "lucide-react"
import type { Dataset } from "@/lib/api"
import { API_URL } from "@/lib/api"

export interface PendingUploadItem {
  id: string | number
  fileName: string
  status: string
}

interface DatasetSectionProps {
  roomId: string | number
  datasets: Dataset[]
  pendingUploads?: PendingUploadItem[]
  selectedDatasetIds: (string | number)[]
  isUploadRunning?: boolean
  onToggleDataset: (datasetId: string | number, checked: boolean) => void
  onAddDatasetClick: () => void
  onOpenSetupCard?: (uploadId: string | number) => void
  onRemoveDataset: (datasetId: string | number) => Promise<void> | void
  onRenameDataset?: (datasetId: string | number, newLabel: string) => Promise<void> | void
}

function DatasetSectionComponent({
  roomId,
  datasets,
  pendingUploads = [],
  selectedDatasetIds,
  isUploadRunning = false,
  onToggleDataset,
  onAddDatasetClick,
  onOpenSetupCard,
  onRemoveDataset,
  onRenameDataset,
}: DatasetSectionProps) {
  const [datasetToDelete, setDatasetToDelete] = useState<Dataset | null>(null)
  const [renamingId, setRenamingId] = useState<string | number | null>(null)
  const [renameValue, setRenameValue] = useState("")

  const handleStartRename = (ds: Dataset) => {
    setRenamingId(ds.id)
    setRenameValue(ds.table_label)
  }

  const handleSaveRename = async (dsId: string | number) => {
    const clean = renameValue.trim()
    if (clean && onRenameDataset) {
      await onRenameDataset(dsId, clean)
    }
    setRenamingId(null)
  }

  return (
    <div className="flex flex-col gap-1.5 select-none">
      {/* Header: DATASETS label + quiet "+ Add dataset" action */}
      <div className="flex items-center justify-between px-1 py-0.5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
          Datasets ({datasets.length})
        </span>
        <button
          type="button"
          onClick={onAddDatasetClick}
          className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-sidebar-foreground transition-colors outline-none focus-visible:underline cursor-pointer"
          title="Add a spreadsheet (.csv, .xlsx)"
        >
          <Plus className="h-3 w-3" />
          <span>Add</span>
        </button>
      </div>

      {/* Dataset & Pending Lists */}
      <div className="flex flex-col gap-1 max-h-[190px] overflow-y-auto pr-0.5">
        {/* 1. Pending Uploads */}
        {pendingUploads.map((up) => {
          const isReview = up.status === "needs_schema_review"
          return (
            <div
              key={`pending-${up.id}`}
              onClick={() => onOpenSetupCard?.(up.id)}
              className="flex items-center justify-between px-2 py-1.5 border border-dashed border-border/80 bg-sidebar-accent/30 text-sidebar-foreground cursor-pointer hover:bg-sidebar-accent/60 transition-colors"
              title={isReview ? "Click to review and approve schema" : "Analyzing spreadsheet schema…"}
            >
              <div className="flex items-center gap-2 min-w-0">
                {isReview ? (
                  <span className="size-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
                ) : (
                  <Loader2 className="size-3 animate-spin text-muted-foreground shrink-0" />
                )}
                <span className="text-xs truncate font-medium text-foreground">
                  {up.fileName.replace(/\.[^/.]+$/, "")}
                </span>
              </div>
              <span className="text-[10px] font-mono text-muted-foreground shrink-0 ml-1">
                {isReview ? "Needs review" : "Analyzing…"}
              </span>
            </div>
          )
        })}

        {/* 2. Approved Datasets */}
        {datasets.length === 0 && pendingUploads.length === 0 ? (
          <div className="px-2 py-2 border border-dashed border-sidebar-border text-[11px] text-muted-foreground text-center">
            No datasets loaded yet
          </div>
        ) : (
          datasets.map((ds) => {
            const isChecked = selectedDatasetIds.includes(ds.id)
            const cleanGrain = (ds.grain || "transaction record")
              .replace(/^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*/i, "")
              .trim()

            return (
              <div
                key={`dataset-${ds.id}`}
                className="group flex flex-col gap-0.5 border border-sidebar-border bg-sidebar px-2 py-1.5 hover:border-sidebar-foreground/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-1.5 min-w-0">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <Checkbox
                      id={`ds-check-${ds.id}`}
                      checked={isChecked}
                      onCheckedChange={(checked) => onToggleDataset(ds.id, Boolean(checked))}
                      aria-label={`Enable ${ds.table_label} for this chat`}
                    />
                    {renamingId === ds.id ? (
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={() => handleSaveRename(ds.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveRename(ds.id)
                          if (e.key === "Escape") setRenamingId(null)
                        }}
                        autoFocus
                        className="text-xs bg-background border border-foreground/30 px-1 py-0.5 outline-none text-foreground font-medium w-full"
                      />
                    ) : (
                      <label
                        htmlFor={`ds-check-${ds.id}`}
                        className="text-xs font-medium text-sidebar-foreground truncate cursor-pointer select-none"
                        title={ds.table_label}
                      >
                        {ds.table_label}
                      </label>
                    )}
                  </div>

                  {/* Overflow actions menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      type="button"
                      className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-0.5 text-muted-foreground hover:text-sidebar-foreground transition-opacity outline-none"
                      aria-label="Dataset options"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-44 text-xs font-mono">
                      {onRenameDataset ? (
                        <DropdownMenuItem onClick={() => handleStartRename(ds)}>
                          <Edit2 className="h-3 w-3 mr-2" />
                          <span>Rename label</span>
                        </DropdownMenuItem>
                      ) : null}
                      {ds.quarantine_count > 0 && ds.upload_id ? (
                        <DropdownMenuItem
                          onClick={() => {
                            window.open(`${API_URL}/uploads/${ds.upload_id}/quarantine.csv`, "_blank")
                          }}
                        >
                          <Download className="h-3 w-3 mr-2" />
                          <span>Download quarantine</span>
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuItem
                        disabled={isUploadRunning}
                        onClick={() => setDatasetToDelete(ds)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-3 w-3 mr-2" />
                        <span>Remove dataset</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                {/* Subtitle: Grain line & row count */}
                <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono pl-5.5 truncate">
                  <span className="truncate max-w-[125px]" title={cleanGrain}>
                    One row = {cleanGrain}
                  </span>
                  <span className="tabular-nums shrink-0 ml-1">
                    {Number(ds.row_count).toLocaleString()} rows
                  </span>
                </div>

                {/* Quarantined link if any */}
                {ds.quarantine_count > 0 && ds.upload_id ? (
                  <div className="pl-5.5 text-[10px] text-muted-foreground font-mono">
                    <a
                      href={`${API_URL}/uploads/${ds.upload_id}/quarantine.csv`}
                      download
                      className="underline decoration-dotted text-amber-500 hover:text-amber-400 transition-colors"
                      title="Download quarantined records"
                    >
                      {Number(ds.quarantine_count).toLocaleString()} set aside (download)
                    </a>
                  </div>
                ) : null}
              </div>
            )
          })
        )}
      </div>

      {/* Delete Confirmation Alert Dialog */}
      <AlertDialog open={Boolean(datasetToDelete)} onOpenChange={(open) => !open && setDatasetToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove dataset?</AlertDialogTitle>
            <AlertDialogDescription className="text-xs leading-relaxed">
              This will permanently delete table <strong className="font-mono text-foreground">{datasetToDelete?.table_name}</strong> ({datasetToDelete?.table_label}), its metadata catalog rows, and any quarantined records. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={async () => {
                if (datasetToDelete) {
                  await onRemoveDataset(datasetToDelete.id)
                  setDatasetToDelete(null)
                }
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export const DatasetSection = React.memo(DatasetSectionComponent)

