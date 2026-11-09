"use client"

import { useCallback } from "react"
import { WorkspacesView } from "@/components/workspaces-view"
import { useResource } from "@/lib/use-resource"
import { API_URL, apiFetch, type WorkspaceSummary } from "@/lib/api"

async function fetchWorkspaces(): Promise<WorkspaceSummary[]> {
  try {
    const res = await apiFetch(`${API_URL}/workspaces`, { cache: "no-store" })
    if (!res.ok) throw new Error("Could not list data rooms.")
    const list = (await res.json()) as WorkspaceSummary[]
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export default function RoomsHubPage() {
  const { data, error, isLoading, mutate } = useResource("workspaces", fetchWorkspaces)

  const handleDelete = useCallback(
    async (id: string | number) => {
      try {
        await apiFetch(`${API_URL}/workspaces/${id}`, { method: "DELETE" })
      } catch {
        // Optimistic delete
      }
      mutate((current) => (current ? current.filter((w) => w.id !== id) : []))
    },
    [mutate]
  )

  return (
    <WorkspacesView
      workspaces={data || []}
      loading={isLoading}
      error={error ? error.message : null}
      onRetry={() => mutate()}
      onDeleteWorkspace={handleDelete}
    />
  )
}
