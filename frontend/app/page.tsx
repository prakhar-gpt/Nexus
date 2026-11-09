import type { Metadata } from "next"
import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"
import { LandingSessionButton } from "@/components/landing-session-button"

export const metadata: Metadata = {
  title: "Nexus · Commercial Due Diligence & Retail Analytics",
  description:
    "Ask your spreadsheets questions. Check every answer. Add a spreadsheet, ask in plain English, and see exactly where every number came from.",
  alternates: {
    canonical: "/",
  },
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between font-mono selection:bg-primary/20 selection:text-foreground">
      {/* 1. Header (56px, hairline) */}
      <header className="border-b border-border bg-background h-14">
        <div className="max-w-[720px] mx-auto px-4 sm:px-6 h-full flex items-center justify-between">
          <Link
            href="/"
            className="text-2xl font-semibold font-heading tracking-tight text-foreground hover:text-primary transition-colors"
          >
            <h1>Nexus</h1>
          </Link>
          <div className="flex items-center gap-4 text-xs">
            <ThemeToggle />
            <LandingSessionButton />
          </div>
        </div>
      </header>

      {/* 2. Hero (Single viewport on desktop) */}
      <main className="max-w-[720px] mx-auto px-4 sm:px-6 py-8 sm:py-12 w-full flex flex-col gap-8 flex-1 justify-center text-left">
        {/* Hero */}
        <section className="flex flex-col gap-4">
          <h2 className="text-3xl sm:text-5xl lg:text-[50px] font-semibold tracking-tight text-foreground leading-[1.1]">
            Ask your spreadsheets questions. Check every answer.
          </h2>
          <p className="text-sm sm:text-base text-muted-foreground leading-relaxed max-w-[620px]">
            Add a spreadsheet, ask in plain English, and see exactly where every number came from.
          </p>
          <div className="flex items-center gap-5 pt-1 text-xs">
            <Link
              href="/signup"
              className="bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 font-medium transition-colors"
            >
              Create account
            </Link>
            <Link
              href="/login"
              className="text-muted-foreground hover:text-foreground transition-colors underline underline-offset-4"
            >
              Sign in
            </Link>
          </div>
        </section>
      </main>
    </div>
  )
}
