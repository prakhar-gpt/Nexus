"use client"

import { useEffect, useState, useSyncExternalStore } from "react"

const TOAST_KEY = "nexus_pending_toast"

let currentToast: string | null = null
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((cb) => cb())
}

export function showToast(message: string) {
  if (typeof window === "undefined") return
  currentToast = message
  sessionStorage.setItem(TOAST_KEY, message)
  notify()
}

export function clearToast() {
  currentToast = null
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(TOAST_KEY)
  }
  notify()
}

export function useToast() {
  const toast = useSyncExternalStore(
    (onStoreChange) => {
      listeners.add(onStoreChange)
      return () => {
        listeners.delete(onStoreChange)
      }
    },
    () => currentToast,
    () => null
  )

  useEffect(() => {
    // Check if there was a pending toast stored before redirect
    const pending = sessionStorage.getItem(TOAST_KEY)
    if (pending) {
      currentToast = pending
      notify()
    }
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => {
      clearToast()
    }, 4000)
    return () => clearTimeout(timer)
  }, [toast])

  return toast
}

