import Link from "next/link"
import { buttonVariants } from "@/components/ui/button"

export default function RoomNotFound() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-6 text-center bg-background">
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground mb-1 select-none">
        Data Room
      </span>
      <h2 className="text-lg font-medium text-foreground tracking-tight">
        This data room doesn't exist or was deleted
      </h2>
      <p className="mt-1 text-xs text-muted-foreground max-w-sm mb-6">
        The workspace may have been archived or the ID is incorrect.
      </p>
      <Link href="/rooms" className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium" })}>
        Back to data rooms
      </Link>
    </div>
  )
}
