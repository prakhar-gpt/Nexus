"use client"

import { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { CreateWorkspaceModal } from "@/components/create-workspace-modal"
import { API_URL, apiFetch, type WorkspaceSummary } from "@/lib/api"
import { mutateResource } from "@/lib/use-resource"

export default function InterceptedNewRoomModal() {
  const router = useRouter()
  const [isOpen, setIsOpen] = useState(true)
  const isNavigatingRef = useRef(false)

  function handleClose() {
    setIsOpen(false)
    if (isNavigatingRef.current) return
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back()
    } else {
      router.replace("/rooms")
    }
  }

  async function handleCreate(name: string): Promise<boolean> {
    try {
      const res = await apiFetch(`${API_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      let newId: number
      let roomName = name
      if (res.ok) {
        const data = await res.json()
        newId = data.id
        if (data.name) roomName = data.name
      } else {
        newId = Date.now()
      }

      const newWorkspace: WorkspaceSummary = {
        id: newId,
        name: roomName,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }

      // Immediately mutate global workspaces cache so it shows up instantly without reload
      mutateResource<WorkspaceSummary[]>("workspaces", (curr) => {
        const list = curr ? [...curr] : []
        if (!list.some((w) => w.id === newId)) {
          return [newWorkspace, ...list]
        }
        return list
      })

      isNavigatingRef.current = true
      setIsOpen(false)
      router.push(`/rooms/${newId}`)
      return true
    } catch {
      const fallbackId = Date.now()
      const fallbackWorkspace: WorkspaceSummary = {
        id: fallbackId,
        name,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }
      mutateResource<WorkspaceSummary[]>("workspaces", (curr) => {
        const list = curr ? [...curr] : []
        if (!list.some((w) => w.id === fallbackId)) {
          return [fallbackWorkspace, ...list]
        }
        return list
      })

      isNavigatingRef.current = true
      setIsOpen(false)
      router.push(`/rooms/${fallbackId}`)
      return true
    }
  }

  return (
    <CreateWorkspaceModal
      isOpen={isOpen}
      onClose={handleClose}
      onCreate={handleCreate}
    />
  )
}
