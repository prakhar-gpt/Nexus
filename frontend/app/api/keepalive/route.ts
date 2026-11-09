import { NextResponse } from "next/server"

export const dynamic = "force-dynamic"

export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "https://nexus-itnt.onrender.com"

  try {
    const res = await fetch(`${backendUrl}/ping`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({
        timestamp: new Date().toISOString(),
        source: "vercel-cron-keepalive",
      }),
    })

    const data = await res.json().catch(() => ({}))
    return NextResponse.json({
      status: "ok",
      backend: backendUrl,
      backendStatus: res.status,
      data,
    })
  } catch (error: any) {
    return NextResponse.json(
      { status: "error", message: error?.message || "Failed to ping backend" },
      { status: 502 }
    )
  }
}
