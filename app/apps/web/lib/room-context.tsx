"use client"

import React, { createContext, useContext } from "react"
import type { Room } from "./api"
import type { RoomStatus } from "./room-status"

export interface RoomContextType {
  room: Room | null
  status: RoomStatus
  isLoading: boolean
  error: Error | null
  mutateRoom: (data?: any) => Promise<any>
}

export const RoomContext = createContext<RoomContextType | undefined>(undefined)

export function useRoom() {
  const ctx = useContext(RoomContext)
  if (!ctx) {
    throw new Error("useRoom must be used within a RoomContext.Provider")
  }
  return ctx
}

