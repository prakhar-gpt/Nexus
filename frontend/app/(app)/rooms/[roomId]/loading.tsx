export default function RoomLoading() {
  return (
    <div className="flex h-full w-full flex-col justify-between p-8 animate-pulse bg-background">
      <div className="mx-auto flex h-full w-full max-w-[720px] flex-col justify-center gap-4">
        <div className="h-8 w-64 bg-muted" />
        <div className="flex flex-col gap-2 mt-4">
          <div className="h-10 w-full bg-muted/40 border border-border" />
          <div className="h-10 w-full bg-muted/40 border border-border" />
          <div className="h-10 w-full bg-muted/40 border border-border" />
        </div>
      </div>
      <div className="mx-auto w-full max-w-[720px] h-14 bg-muted/30 border border-border mt-auto" />
    </div>
  )
}

