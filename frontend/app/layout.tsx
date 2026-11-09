import type { Metadata } from "next"
import { JetBrains_Mono, Playfair_Display } from "next/font/google"
import "./globals.css"
import { ThemeScript } from "@/components/theme-script"
import { Toaster } from "@/components/ui/toaster"
import { AuthProvider } from "@/lib/auth/provider"
import { cn } from "@/lib/utils"

export const metadata: Metadata = {
  title: "Nexus · Commercial Due Diligence & Retail Analytics",
  description: "Retail Data Room Copilot for Commercial Due Diligence",
}

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600"],
  display: "swap",
})

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "500", "600", "700"],
  display: "swap",
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
      className={cn("antialiased font-sans", jetbrains.variable, playfair.variable)}
    >
      <head>
        <ThemeScript />
      </head>
      <body className="min-h-screen bg-background text-foreground">
        <AuthProvider>{children}</AuthProvider>
        <Toaster />
      </body>
    </html>
  )
}
