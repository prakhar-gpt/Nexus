import type { Metadata } from "next"
import { JetBrains_Mono } from "next/font/google"

import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthProvider } from "@/lib/auth-context"
import { cn } from "@/lib/utils"

export const metadata: Metadata = {
  title: "Nexus — Retail Data Room Copilot",
  description: "Retail Data Room Copilot for Commercial Due Diligence",
}

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-sans",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn("antialiased font-sans", jetbrains.variable)}
    >
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
