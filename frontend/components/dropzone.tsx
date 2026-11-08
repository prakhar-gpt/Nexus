"use client"

import { useState, useRef } from "react"
import { UploadCloud, AlertCircle, FileSpreadsheet } from "lucide-react"

interface DropzoneProps {
  onFileSelect: (file: File) => void
  disabled?: boolean
  currentFileName?: string | null
  errorReason?: string | null
}

const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50MB

export function Dropzone({
  onFileSelect,
  disabled = false,
  currentFileName,
  errorReason,
}: DropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function validateAndSelect(file: File) {
    setLocalError(null)

    // Check macro-enabled files (.xlsm)
    if (file.name.endsWith(".xlsm")) {
      setLocalError("Macro-enabled workbooks (.xlsm) are not permitted for security reasons.")
      return
    }

    // Check file type
    const validExts = [".csv", ".xlsx", ".xls"]
    const hasValidExt = validExts.some((ext) => file.name.toLowerCase().endsWith(ext))
    if (!hasValidExt) {
      setLocalError("Invalid file type. Please upload a standard .csv or .xlsx spreadsheet.")
      return
    }

    // Check size limit
    if (file.size > MAX_SIZE_BYTES) {
      setLocalError("File exceeds 50MB limit. Split the dataset or upload a compressed file.")
      return
    }

    // Check empty file
    if (file.size === 0) {
      setLocalError("The selected file is empty (0 bytes).")
      return
    }

    onFileSelect(file)
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    if (!disabled) setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    if (disabled) return
    const file = e.dataTransfer.files?.[0]
    if (file) {
      validateAndSelect(file)
    }
  }

  const displayError = errorReason || localError

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        tabIndex={disabled ? -1 : 0}
        role="button"
        aria-label="Upload sales spreadsheet dropzone"
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault()
            fileInputRef.current?.click()
          }
        }}
        className={`flex flex-col items-center justify-center p-6 border border-dashed transition-colors cursor-pointer select-none text-center ${
          isDragOver
            ? "border-foreground/40 bg-accent/40"
            : "border-border hover:border-foreground/30 hover:bg-accent/20"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          disabled={disabled}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              validateAndSelect(file)
            }
            e.target.value = ""
          }}
        />

        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted/60 text-muted-foreground mb-2">
          {currentFileName ? (
            <FileSpreadsheet className="h-4 w-4" />
          ) : (
            <UploadCloud className="h-4 w-4" />
          )}
        </div>

        <p className="text-xs font-medium text-foreground">
          {currentFileName ? (
            <span>{currentFileName}</span>
          ) : (
            <span>Drop a .csv or .xlsx here, or browse</span>
          )}
        </p>

        <p className="text-[11px] text-muted-foreground mt-1">
          CSV or Excel files up to 50MB
        </p>
      </div>

      {displayError ? (
        <div
          role="alert"
          className="flex items-start gap-1.5 p-2 bg-destructive/10 border border-destructive/20 text-destructive text-xs"
        >
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>{displayError}</span>
        </div>
      ) : null}
    </div>
  )
}

