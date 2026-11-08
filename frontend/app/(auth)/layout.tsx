import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const hasSession = cookieStore.has("nexus_session")

  if (hasSession) {
    redirect("/rooms")
  }

  return <>{children}</>
}

