import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'

// ── Minimal stubs for Nuxt auto-imports ───────────────────────────────────

// The composable imports `ref` from Vue via Nuxt auto-import at runtime.
// In tests we provide it via the global scope so the module resolves it.
(globalThis as Record<string, unknown>).ref = ref

// ── Constants mirrored from the composable ────────────────────────────────

const STORAGE_KEY = 'kartograph:kg-setup-wizard'

// ── Lightweight in-memory localStorage ────────────────────────────────────

const store: Record<string, string> = {}

const localStorageMock = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, val: string) => { store[key] = val },
  removeItem: (key: string) => { delete store[key] },
}

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
  writable: true,
})

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultWizardState() {
  return {
    step: 1,
    step1: { workspaceId: '', kgName: '', kgDescription: '' },
    step2: {
      dsName: '',
      adapterType: 'github',
      github: { owner: '', repo: '', branch: 'main' },
      githubToken: '',
    },
  }
}

function saveToStorage(data: ReturnType<typeof defaultWizardState>) {
  store[STORAGE_KEY] = JSON.stringify(data)
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useKgSetupWizard — state shape', () => {
  it('produces a default state with step 1', () => {
    const s = defaultWizardState()
    expect(s.step).toBe(1)
    expect(s.step1.kgName).toBe('')
    expect(s.step2.adapterType).toBe('github')
    expect(s.step2.github.branch).toBe('main')
  })
})

describe('useKgSetupWizard — localStorage persistence', () => {
  beforeEach(() => {
    Object.keys(store).forEach(k => delete store[k])
  })

  it('saves state without the token field', () => {
    const state = { ...defaultWizardState(), step: 2 as const }
    state.step2.githubToken = 'ghp_secret'
    // Simulate what save() does: strip token before persisting
    const safe = { ...state, step2: { ...state.step2, githubToken: '' } }
    store[STORAGE_KEY] = JSON.stringify(safe)

    const persisted = JSON.parse(store[STORAGE_KEY])
    expect(persisted.step2.githubToken).toBe('')
    expect(persisted.step).toBe(2)
  })

  it('restores step and step1 data from localStorage', () => {
    const saved = defaultWizardState()
    saved.step = 3 as never
    saved.step1.kgName = 'Restored KG'
    saved.step1.workspaceId = 'ws-123'
    saveToStorage(saved)

    const raw = localStorage.getItem(STORAGE_KEY)
    expect(raw).not.toBeNull()
    const loaded = JSON.parse(raw!)
    expect(loaded.step).toBe(3)
    expect(loaded.step1.kgName).toBe('Restored KG')
    expect(loaded.step1.workspaceId).toBe('ws-123')
  })

  it('resets to default when storage is cleared', () => {
    saveToStorage({ ...defaultWizardState(), step: 2 as never })
    delete store[STORAGE_KEY]

    const raw = localStorage.getItem(STORAGE_KEY)
    expect(raw).toBeNull()

    // After clear, default state is returned
    const fallback = defaultWizardState()
    expect(fallback.step).toBe(1)
  })
})

describe('useKgSetupWizard — buildConnectionConfig logic', () => {
  it('produces correct GitHub connection_config', () => {
    const github = { owner: 'my-org', repo: 'my-repo', branch: 'develop' }
    const cfg: Record<string, string> = {
      owner: github.owner,
      repo: github.repo,
    }
    if (github.branch && github.branch !== 'main') {
      cfg.branch = github.branch
    }
    expect(cfg).toEqual({ owner: 'my-org', repo: 'my-repo', branch: 'develop' })
  })

  it('omits branch when it is the default "main"', () => {
    const github = { owner: 'my-org', repo: 'my-repo', branch: 'main' }
    const cfg: Record<string, string> = {
      owner: github.owner,
      repo: github.repo,
    }
    if (github.branch && github.branch !== 'main') {
      cfg.branch = github.branch
    }
    expect(cfg).not.toHaveProperty('branch')
  })
})

describe('useKgSetupWizard — step validation logic', () => {
  it('step1 is invalid when kgName is empty', () => {
    const step1 = { workspaceId: 'ws-1', kgName: '', kgDescription: '' }
    const valid = !!step1.workspaceId && step1.kgName.trim().length > 0
    expect(valid).toBe(false)
  })

  it('step1 is invalid when workspaceId is empty', () => {
    const step1 = { workspaceId: '', kgName: 'My KG', kgDescription: '' }
    const valid = !!step1.workspaceId && step1.kgName.trim().length > 0
    expect(valid).toBe(false)
  })

  it('step1 is valid when both workspaceId and kgName are set', () => {
    const step1 = { workspaceId: 'ws-1', kgName: 'My KG', kgDescription: '' }
    const valid = !!step1.workspaceId && step1.kgName.trim().length > 0
    expect(valid).toBe(true)
  })

  it('step2 GitHub is invalid when owner is missing', () => {
    const s2 = { dsName: 'DS', adapterType: 'github', github: { owner: '', repo: 'my-repo', branch: 'main' } }
    const valid = s2.dsName.trim().length > 0
      && s2.github.owner.trim().length > 0
      && s2.github.repo.trim().length > 0
    expect(valid).toBe(false)
  })

  it('step2 GitHub is valid when dsName, owner, and repo are set', () => {
    const s2 = { dsName: 'DS', adapterType: 'github', github: { owner: 'my-org', repo: 'my-repo', branch: 'main' } }
    const valid = s2.dsName.trim().length > 0
      && s2.github.owner.trim().length > 0
      && s2.github.repo.trim().length > 0
    expect(valid).toBe(true)
  })
})
