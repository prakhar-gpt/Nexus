import type { Metadata } from "next"
import { cookies } from "next/headers"
import Link from "next/link"

export const metadata: Metadata = {
  title: "Nexus · Retail Data Room Copilot",
  description:
    "Ask your spreadsheets questions. Check every answer. Nexus is a data room copilot for commercial diligence.",
  alternates: {
    canonical: "/",
  },
}

export default async function LandingPage() {
  const cookieStore = await cookies()
  const hasSession = cookieStore.has("nexus_session")
  const allowSignup = process.env.ALLOW_SIGNUP !== "false"

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-mono selection:bg-primary/20 selection:text-foreground">
      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link
            href="/"
            className="text-base font-bold tracking-tight text-foreground hover:text-primary transition-colors"
          >
            Nexus
          </Link>
          <div className="flex items-center gap-4 text-xs">
            {hasSession ? (
              <Link
                href="/rooms"
                className="bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-1.5 font-medium transition-colors rounded-[var(--radius)]"
              >
                Open data room
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className={`text-muted-foreground hover:text-foreground transition-colors ${
                    !allowSignup
                      ? "bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-1.5 font-medium rounded-[var(--radius)]"
                      : ""
                  }`}
                >
                  Sign in
                </Link>
                {allowSignup && (
                  <Link
                    href="/signup"
                    className="bg-primary text-primary-foreground hover:bg-primary/90 px-3 py-1.5 font-medium transition-colors rounded-[var(--radius)]"
                  >
                    Create account
                  </Link>
                )}
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto px-6 py-16 sm:py-24 w-full flex flex-col gap-16 text-left">
        {/* Hero Section */}
        <section className="flex flex-col gap-6 max-w-2xl">
          <h1 className="text-3xl sm:text-[32px] font-semibold tracking-tight text-foreground leading-[1.2]">
            Ask your spreadsheets questions. Check every answer.
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Nexus is a data room copilot for commercial diligence. Add a spreadsheet,
            ask in plain English, and see the query behind every number.
          </p>
          <div className="pt-2">
            {hasSession ? (
              <Link
                href="/rooms"
                className="inline-flex items-center justify-center bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-xs font-semibold tracking-tight transition-colors rounded-[var(--radius)]"
              >
                Go to data rooms
              </Link>
            ) : (
              <Link
                href={allowSignup ? "/signup" : "/login"}
                className="inline-flex items-center justify-center bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 text-xs font-semibold tracking-tight transition-colors rounded-[var(--radius)]"
              >
                {allowSignup ? "Create account" : "Sign in to data room"}
              </Link>
            )}
          </div>
        </section>

        {/* How It Works Section */}
        <section className="border-t border-border pt-12 flex flex-col gap-6">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            How it works
          </span>
          <div className="grid grid-cols-1 divide-y divide-border border border-border rounded-[var(--radius)]">
            <div className="p-4 flex items-start gap-4">
              <span className="text-xs text-muted-foreground shrink-0 font-medium">01</span>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-foreground">Add a dataset</span>
                <span className="text-xs text-muted-foreground leading-relaxed">
                  Upload CSV or Excel files. Nexus profiles column types, detects table grain,
                  and stages a custom relational table under your review.
                </span>
              </div>
            </div>

            <div className="p-4 flex items-start gap-4">
              <span className="text-xs text-muted-foreground shrink-0 font-medium">02</span>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-foreground">Ask a question</span>
                <span className="text-xs text-muted-foreground leading-relaxed">
                  Query margins, category profitability, promotions, or trends in natural language.
                  Nexus plans read-only SQL queries and executes arithmetic in a sandboxed runtime.
                </span>
              </div>
            </div>

            <div className="p-4 flex items-start gap-4">
              <span className="text-xs text-muted-foreground shrink-0 font-medium">03</span>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-foreground">Check the query</span>
                <span className="text-xs text-muted-foreground leading-relaxed">
                  Every figure cited in an answer is cross-checked against raw query outputs by an
                  isolated verifier. Inspect the exact SQL and row evidence behind every claim.
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Example Verification Block */}
        <section className="border-t border-border pt-12 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Example answer
            </span>
            <span className="text-[10px] text-muted-foreground border border-border px-1.5 py-0.5 rounded-[var(--radius)]">
              Static preview
            </span>
          </div>

          <div className="border border-border bg-card p-5 rounded-[var(--radius)] flex flex-col gap-4 text-xs leading-relaxed">
            <div className="flex items-center gap-2 text-muted-foreground border-b border-border pb-3">
              <span className="font-medium text-foreground">User:</span>
              <span>Which sub-category generated the lowest gross profit in 2024?</span>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-start gap-2">
                <span className="font-semibold text-primary">Nexus:</span>
                <div className="flex flex-col gap-2 text-foreground">
                  <p>
                    <strong>Tables</strong> generated the lowest gross profit in 2024, recording a net
                    loss of <strong>-$17,725.48</strong> on <strong>$206,965.53</strong> in total sales.
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Average discount applied to Tables was 26.1%, compared to a category benchmark of 14.8%.
                  </p>
                </div>
              </div>

              {/* Collapsed Query Preview */}
              <div className="mt-2 border border-border bg-muted/40 p-3 rounded-[var(--radius)] flex flex-col gap-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">Verified by Number Checker</span>
                  <span className="text-muted-foreground font-mono">1 query · 17 rows</span>
                </div>
                <pre className="text-[11px] text-foreground font-mono overflow-x-auto bg-background p-2 border border-border">
                  {`SELECT sub_category, SUM(sales) AS total_sales, SUM(profit) AS total_profit
FROM user_data.ds_superstore
WHERE order_date >= '2024-01-01'
GROUP BY sub_category
ORDER BY total_profit ASC
LIMIT 1;`}
                </pre>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8 text-xs text-muted-foreground">
        <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="font-bold text-foreground">Nexus</span>
            <span>·</span>
            <span>Answers are checked against query results. Verify before sharing.</span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Commercial Due Diligence</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
