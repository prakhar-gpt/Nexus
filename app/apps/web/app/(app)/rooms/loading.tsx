export default function RoomsLoading() {
  return (
    <div className="flex min-h-screen w-full flex-col bg-background animate-pulse">
      <header className="h-14 border-b border-border px-6 flex items-center justify-between">
        <div className="h-4 w-28 bg-muted" />
        <div className="h-8 w-24 bg-muted" />
      </header>
      <main className="max-w-[960px] mx-auto w-full px-6 py-10 flex flex-col">
        <div className="h-8 w-44 bg-muted" />
        <div className="h-4 w-72 bg-muted/60 mt-2" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-[170px] border border-border bg-card p-5 flex flex-col justify-between"
            >
              <div className="flex flex-col gap-2">
                <div className="h-4 bg-muted w-3/4" />
                <div className="h-3 bg-muted/60 w-1/2 mt-2" />
              </div>
              <div className="h-3 bg-muted/40 w-1/3" />
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}

