import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export default async function Page() {
  const cookieStore = await cookies()
  const hasSession = cookieStore.has("nexus_session")
  redirect(hasSession ? "/rooms" : "/login")
}
