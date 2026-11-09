"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { registerUnauthorizedCleanup } from "./api"

type Fetcher<T> = () => Promise<T>

interface ResourceState<T> {
  data: T | undefined
  error: Error | null
  isLoading: boolean
}

// Global in-memory cache and promise deduplication map
const resourceCache = new Map<string, any>()
const inFlightRequests = new Map<string, Promise<any>>()
const subscribers = new Map<string, Set<() => void>>()

function notify(key: string) {
  const subs = subscribers.get(key)
  if (subs) {
    subs.forEach((cb) => cb())
  }
}

export function clearResourceCache() {
  resourceCache.clear()
  inFlightRequests.clear()
  subscribers.forEach((subs) => {
    subs.forEach((cb) => cb())
  })
}

// Auto-register clearResourceCache on 401 unauthenticated
registerUnauthorizedCleanup(clearResourceCache)

export function mutateResource<T>(
  key: string,
  newData?: T | Promise<T> | ((curr?: T) => T | Promise<T>)
): Promise<T | undefined> | T | undefined {
  if (typeof newData === "function") {
    const current = resourceCache.get(key)
    const result = (newData as Function)(current)
    if (result instanceof Promise) {
      return result.then((resolved) => {
        resourceCache.set(key, resolved)
        notify(key)
        return resolved
      })
    }
    resourceCache.set(key, result)
    notify(key)
    return result
  }
  if (newData !== undefined) {
    if (newData instanceof Promise) {
      return newData.then((resolved) => {
        resourceCache.set(key, resolved)
        notify(key)
        return resolved
      })
    }
    resourceCache.set(key, newData)
    notify(key)
    return newData
  }
  // When called without arguments, revalidate subscribers without wiping existing cached data
  notify(key)
  return resourceCache.get(key)
}

export function useResource<T>(key: string | null, fetcher: Fetcher<T>) {
  // Derive state from key so switching keys never shows another key's data
  const [currentKey, setCurrentKey] = useState<string | null>(key)
  const [state, setState] = useState<ResourceState<T>>(() => ({
    data: key ? resourceCache.get(key) : undefined,
    error: null,
    isLoading: key ? !resourceCache.has(key) : false,
  }))

  if (key !== currentKey) {
    setCurrentKey(key)
    setState({
      data: key ? resourceCache.get(key) : undefined,
      error: null,
      isLoading: key ? !resourceCache.has(key) : false,
    })
  }

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const executeFetch = useCallback(
    async (isBackground = false) => {
      if (!key) return

      if (!isBackground && !resourceCache.has(key)) {
        setState((prev) => ({ ...prev, isLoading: true }))
      }

      try {
        let promise = inFlightRequests.get(key)
        if (!promise) {
          promise = fetcherRef.current().finally(() => {
            inFlightRequests.delete(key)
          })
          inFlightRequests.set(key, promise)
        }

        const result = await promise
        resourceCache.set(key, result)
        setState({ data: result, error: null, isLoading: false })
        notify(key)
        return result
      } catch (err: any) {
        const errorObj = err instanceof Error ? err : new Error(String(err))
        setState((prev) => ({ ...prev, error: errorObj, isLoading: false }))
        throw errorObj
      }
    },
    [key]
  )

  useEffect(() => {
    if (!key) return

    // Register subscriber for sync across multiple components using the same key
    if (!subscribers.has(key)) {
      subscribers.set(key, new Set())
    }
    const update = () => {
      setState((prev) => {
        const nextData = resourceCache.get(key)
        return {
          ...prev,
          data: nextData !== undefined ? nextData : prev.data,
        }
      })
    }
    subscribers.get(key)?.add(update)

    // Initial fetch or revalidation (catch errors so they don't cause unhandled promise rejection)
    executeFetch(resourceCache.has(key)).catch(() => {})

    // Revalidate on window focus
    const onFocus = () => {
      if (document.visibilityState === "visible") {
        executeFetch(true).catch(() => {})
      }
    }
    window.addEventListener("focus", onFocus)
    window.addEventListener("visibilitychange", onFocus)

    return () => {
      subscribers.get(key)?.delete(update)
      window.removeEventListener("focus", onFocus)
      window.removeEventListener("visibilitychange", onFocus)
    }
  }, [key, executeFetch])

  const mutate = useCallback(
    async (newData?: T | Promise<T> | ((curr?: T) => T | Promise<T>)) => {
      if (!key) return
      if (typeof newData === "function") {
        const current = resourceCache.get(key)
        const updated = await (newData as Function)(current)
        resourceCache.set(key, updated)
        setState({ data: updated, error: null, isLoading: false })
        notify(key)
        return updated
      }
      if (newData !== undefined) {
        const resolved = await newData
        resourceCache.set(key, resolved)
        setState({ data: resolved, error: null, isLoading: false })
        notify(key)
        return resolved
      }
      // Re-fetch if called with no arguments
      return executeFetch(false).catch(() => {})
    },
    [key, executeFetch]
  )

  return {
    data: state.data,
    error: state.error,
    isLoading: state.isLoading,
    mutate,
  }
}
