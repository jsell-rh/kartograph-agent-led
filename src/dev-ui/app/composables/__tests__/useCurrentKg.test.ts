import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, computed } from 'vue'

// ── Stub Nuxt auto-imports ─────────────────────────────────────────────────
// useState must share a key→ref registry so all callers within a test get the
// same reactive ref (mimicking Nuxt's useState behaviour).

const stateRegistry = new Map<string, ReturnType<typeof ref>>()

;(globalThis as Record<string, unknown>).useState = <T>(
  key: string,
  init: () => T,
): ReturnType<typeof ref<T>> => {
  if (!stateRegistry.has(key)) {
    stateRegistry.set(key, ref(init()))
  }
  return stateRegistry.get(key) as ReturnType<typeof ref<T>>
}

;(globalThis as Record<string, unknown>).computed = computed
;(globalThis as Record<string, unknown>).ref = ref

// ── localStorage mock ──────────────────────────────────────────────────────

const store: Record<string, string> = {}
const localStorageMock = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, val: string) => { store[key] = val },
  removeItem: (key: string) => { delete store[key] },
}
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true })

// ── Import composable under test ───────────────────────────────────────────

const { useCurrentKg } = await import('../useCurrentKg')

// ── Helpers ────────────────────────────────────────────────────────────────

function ws(id: string) {
  return { id, name: `Workspace ${id}`, tenant_id: 'tenant-1', created_at: '' }
}

function kg(id: string, wsId: string) {
  return { id, name: `KG ${id}`, workspace_id: wsId, created_at: '' }
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useCurrentKg', () => {
  beforeEach(() => {
    // Reset shared state and localStorage between tests
    stateRegistry.clear()
    for (const key of Object.keys(store)) delete store[key]
  })

  describe('reconcileWorkspaces', () => {
    it('selects the first workspace when none is stored', () => {
      const { reconcileWorkspaces, currentWorkspaceId } = useCurrentKg()
      reconcileWorkspaces([ws('ws-1'), ws('ws-2')])
      expect(currentWorkspaceId.value).toBe('ws-1')
    })

    it('restores a previously stored workspace when still valid', () => {
      store['kartograph:current-workspace'] = 'ws-2'
      const { reconcileWorkspaces, currentWorkspaceId } = useCurrentKg()
      reconcileWorkspaces([ws('ws-1'), ws('ws-2')])
      expect(currentWorkspaceId.value).toBe('ws-2')
    })

    it('falls back to first workspace when stored workspace no longer exists', () => {
      store['kartograph:current-workspace'] = 'ws-old'
      const { reconcileWorkspaces, currentWorkspaceId } = useCurrentKg()
      reconcileWorkspaces([ws('ws-1'), ws('ws-2')])
      expect(currentWorkspaceId.value).toBe('ws-1')
    })

    it('clears selection when the workspace list is empty', () => {
      const { reconcileWorkspaces, currentWorkspaceId } = useCurrentKg()
      currentWorkspaceId.value = 'ws-1'
      reconcileWorkspaces([])
      expect(currentWorkspaceId.value).toBeNull()
    })
  })

  describe('reconcileKgs', () => {
    it('selects the first KG when none is stored', () => {
      const { reconcileKgs, currentKgId } = useCurrentKg()
      reconcileKgs([kg('kg-1', 'ws-1'), kg('kg-2', 'ws-1')])
      expect(currentKgId.value).toBe('kg-1')
    })

    it('restores a previously stored KG when still valid', () => {
      store['kartograph:current-kg'] = 'kg-2'
      const { reconcileKgs, currentKgId } = useCurrentKg()
      reconcileKgs([kg('kg-1', 'ws-1'), kg('kg-2', 'ws-1')])
      expect(currentKgId.value).toBe('kg-2')
    })

    it('falls back to first KG when stored KG no longer exists', () => {
      store['kartograph:current-kg'] = 'kg-old'
      const { reconcileKgs, currentKgId } = useCurrentKg()
      reconcileKgs([kg('kg-1', 'ws-1'), kg('kg-2', 'ws-1')])
      expect(currentKgId.value).toBe('kg-1')
    })

    it('bumps kgVersion after reconciling', () => {
      const { reconcileKgs, kgVersion } = useCurrentKg()
      const before = kgVersion.value
      reconcileKgs([kg('kg-1', 'ws-1')])
      expect(kgVersion.value).toBe(before + 1)
    })

    it('sets kgsLoaded to true after reconciling', () => {
      const { reconcileKgs, kgsLoaded } = useCurrentKg()
      expect(kgsLoaded.value).toBe(false)
      reconcileKgs([kg('kg-1', 'ws-1')])
      expect(kgsLoaded.value).toBe(true)
    })

    it('clears KG and bumps version when the KG list is empty', () => {
      const { reconcileKgs, currentKgId, kgVersion } = useCurrentKg()
      currentKgId.value = 'kg-1'
      const before = kgVersion.value
      reconcileKgs([])
      expect(currentKgId.value).toBeNull()
      expect(kgVersion.value).toBe(before + 1)
    })
  })

  describe('switchWorkspace', () => {
    it('clears KG selection when the workspace changes', () => {
      const { switchWorkspace, currentKgId, kgs } = useCurrentKg()
      currentKgId.value = 'kg-1'
      kgs.value = [kg('kg-1', 'ws-1')]
      switchWorkspace('ws-2')
      expect(currentKgId.value).toBeNull()
      expect(kgs.value).toHaveLength(0)
    })

    it('is a no-op when switching to the current workspace', () => {
      const { switchWorkspace, currentWorkspaceId } = useCurrentKg()
      currentWorkspaceId.value = 'ws-1'
      switchWorkspace('ws-1')
      // value unchanged — no side effects
      expect(currentWorkspaceId.value).toBe('ws-1')
    })
  })

  describe('switchKg', () => {
    it('updates currentKgId and bumps kgVersion', () => {
      const { switchKg, currentKgId, kgVersion } = useCurrentKg()
      const before = kgVersion.value
      switchKg('kg-2')
      expect(currentKgId.value).toBe('kg-2')
      expect(kgVersion.value).toBe(before + 1)
    })

    it('is a no-op when switching to the current KG', () => {
      const { switchKg, currentKgId, kgVersion } = useCurrentKg()
      currentKgId.value = 'kg-1'
      const before = kgVersion.value
      switchKg('kg-1')
      expect(kgVersion.value).toBe(before)
    })
  })

  describe('derived state', () => {
    it('currentKg returns the full KG object for the selected ID', () => {
      const { reconcileKgs, currentKg } = useCurrentKg()
      reconcileKgs([kg('kg-1', 'ws-1'), kg('kg-2', 'ws-1')])
      expect(currentKg.value?.id).toBe('kg-1')
    })

    it('hasKg is true when a KG is selected', () => {
      const { switchKg, hasKg } = useCurrentKg()
      switchKg('kg-1')
      expect(hasKg.value).toBe(true)
    })

    it('hasKg is false when no KG is selected', () => {
      const { clearKg, hasKg } = useCurrentKg()
      clearKg()
      expect(hasKg.value).toBe(false)
    })
  })
})
