"use client"

import * as React from "react"
import { Checkbox as CheckboxPrimitive } from "@base-ui/react/checkbox"
import { CheckIcon } from "lucide-react"
import { cn } from "@/lib/utils"

function Checkbox({
  className,
  ...props
}: CheckboxPrimitive.Root.Props) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer border-border text-background focus-visible:border-foreground focus-visible:ring-1 focus-visible:ring-foreground size-3.5 shrink-0 border transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center cursor-pointer data-[checked]:bg-foreground data-[checked]:border-foreground",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="flex items-center justify-center text-background">
        <CheckIcon className="size-2.5 stroke-[3]" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }

