import type { KnowledgeGraphResponse, WorkspaceResponse } from '~/types'

const WS_STORAGE_KEY = 'kartograph:current-workspace'
const KG_STORAGE_KEY = 'kartograph:current-kg'

/**
 * Centralised Knowledge Graph context composable.
 *
 * Manages the currently-selected workspace + KG across the whole application,
 * persisted in localStorage so it survives page refreshes. Shared via Nuxt
 * `useState` so every component and composable reads the same reactive ref.
 *
 * A monotonically-increasing `kgVersion` counter is bumped on every switch
 * so watcher-based pages can re-fetch automatically.
 */
export function useCurrentKg() {
  const currentWorkspaceId = useState<string | null>('kg:workspace', () => null)
  const currentKgId = useState<string | null>('kg:current', () => null)
  const kgVersion = useState<number>('kg:version', () => 0)

  // Full list state (populated by the layout on boot)
  const workspaces = useState<WorkspaceResponse[]>('kg:workspaces', () => [])
  const kgs = useState<KnowledgeGraphResponse[]>('kg:list', () => [])
  const workspacesLoading = useState<boolean>('kg:ws-loading', () => false)
  const kgsLoading = useState<boolean>('kg:kgs-loading', () => false)
  const kgsLoaded = useState<boolean>('kg:loaded', () => false)

  function persistWorkspace(id: string | null) {
    if (typeof window === 'undefined') return
    id ? localStorage.setItem(WS_STORAGE_KEY, id) : localStorage.removeItem(WS_STORAGE_KEY)
  }

  function persistKg(id: string | null) {
    if (typeof window === 'undefined') return
    id ? localStorage.setItem(KG_STORAGE_KEY, id) : localStorage.removeItem(KG_STORAGE_KEY)
  }

  function restoreWorkspace(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem(WS_STORAGE_KEY)
  }

  function restoreKg(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem(KG_STORAGE_KEY)
  }

  function switchWorkspace(wsId: string) {
    if (wsId === currentWorkspaceId.value) return
    currentWorkspaceId.value = wsId
    persistWorkspace(wsId)
    // Clear KG selection when workspace changes
    currentKgId.value = null
    persistKg(null)
    kgs.value = []
    kgsLoaded.value = false
  }

  function switchKg(kgId: string, kgName?: string) {
    if (kgId === currentKgId.value) return
    currentKgId.value = kgId
    persistKg(kgId)
    kgVersion.value++
  }

  function clearKg() {
    currentKgId.value = null
    persistKg(null)
    kgVersion.value++
  }

  /**
   * Called after workspaces are loaded. Restores or auto-selects a workspace.
   */
  function reconcileWorkspaces(fetchedWorkspaces: WorkspaceResponse[]) {
    workspaces.value = fetchedWorkspaces

    if (fetchedWorkspaces.length === 0) {
      currentWorkspaceId.value = null
      persistWorkspace(null)
      return
    }

    const stored = restoreWorkspace()
    const stillValid = stored && fetchedWorkspaces.some(w => w.id === stored)

    if (stillValid) {
      currentWorkspaceId.value = stored
    } else {
      const first = fetchedWorkspaces[0]
      if (first) {
        currentWorkspaceId.value = first.id
        persistWorkspace(first.id)
      }
    }
  }

  /**
   * Called after KGs for the current workspace are loaded.
   */
  function reconcileKgs(fetchedKgs: KnowledgeGraphResponse[]) {
    kgs.value = fetchedKgs
    kgsLoaded.value = true

    if (fetchedKgs.length === 0) {
      currentKgId.value = null
      persistKg(null)
      kgVersion.value++
      return
    }

    const stored = restoreKg()
    const stillValid = stored && fetchedKgs.some(k => k.id === stored)

    if (stillValid) {
      currentKgId.value = stored
    } else {
      const first = fetchedKgs[0]
      if (first) {
        currentKgId.value = first.id
        persistKg(first.id)
      }
    }

    kgVersion.value++
  }

  const currentWorkspace = computed(() =>
    workspaces.value.find(w => w.id === currentWorkspaceId.value) ?? null,
  )

  const currentKg = computed(() =>
    kgs.value.find(k => k.id === currentKgId.value) ?? null,
  )

  const currentKgName = computed(() => currentKg.value?.name ?? null)

  const hasKg = computed(() => !!currentKgId.value)

  return {
    currentWorkspaceId,
    currentKgId,
    currentKgName,
    currentKg,
    currentWorkspace,
    workspaces,
    kgs,
    kgVersion,
    workspacesLoading,
    kgsLoading,
    kgsLoaded,
    hasKg,
    switchWorkspace,
    switchKg,
    clearKg,
    reconcileWorkspaces,
    reconcileKgs,
  }
}
