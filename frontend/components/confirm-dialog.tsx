"use client"

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

interface ConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  variant?: "default" | "destructive"
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = "Delete",
  cancelText = "Cancel",
  variant = "destructive",
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent className="max-w-[420px] rounded-[var(--radius)] border border-border bg-popover p-6 shadow-none">
        <AlertDialogHeader className="text-left gap-1.5 p-0">
          <AlertDialogTitle className="text-base font-medium text-foreground">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-xs text-muted-foreground leading-normal">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="mt-6 flex-row justify-end gap-2 border-0 bg-transparent p-0">
          <AlertDialogCancel
            variant="ghost"
            onClick={onClose}
            className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
          >
            {cancelText}
          </AlertDialogCancel>
          <AlertDialogAction
            variant={variant}
            onClick={() => {
              onConfirm()
              onClose()
            }}
            className="h-8 px-3 text-xs"
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
