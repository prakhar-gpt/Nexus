import Link from "next/link"
import { buttonVariants } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background px-4 text-center">
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground mb-1 select-none">
        404
      </span>
      <h1 className="text-xl font-medium text-foreground tracking-tight">
        Page not found
      </h1>
      <p className="mt-1 text-xs text-muted-foreground max-w-sm mb-6">
        The requested URL does not exist or has been moved.
      </p>
      <Link href="/rooms" className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium" })}>
        Back to data rooms
      </Link>
    </div>
  )
}
