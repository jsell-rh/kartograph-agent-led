/**
 * Wizard state for the guided KnowledgeGraph + DataSource setup flow.
 *
 * State persists to localStorage so progress survives navigation or a page
 * refresh.  Call `reset()` after a successful submit.
 */

const STORAGE_KEY = 'kartograph:kg-setup-wizard'

export type AdapterType = 'github'

/** Per-adapter labeled connection fields (non-secret). */
export interface GitHubConnectionFields {
  owner: string   // GitHub org or user
  repo: string    // Repository name
  branch: string  // Branch to index (default: main)
}

/** Per-adapter labeled credential fields (secret, encrypted at rest). */
export interface GitHubCredentialFields {
  token: string   // GitHub Personal Access Token (ghp_…)
}

export interface WizardStep1 {
  workspaceId: string
  kgName: string
  kgDescription: string
}

export interface WizardStep2 {
  dsName: string
  adapterType: AdapterType
  // GitHub adapter
  github: GitHubConnectionFields
  githubToken: string
}

export interface WizardState {
  step: 1 | 2 | 3
  step1: WizardStep1
  step2: WizardStep2
}

const defaultState = (): WizardState => ({
  step: 1,
  step1: {
    workspaceId: '',
    kgName: '',
    kgDescription: '',
  },
  step2: {
    dsName: '',
    adapterType: 'github',
    github: { owner: '', repo: '', branch: 'main' },
    githubToken: '',
  },
})

function load(): WizardState {
  if (typeof window === 'undefined') return defaultState()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    return { ...defaultState(), ...JSON.parse(raw) }
  } catch {
    return defaultState()
  }
}

function save(state: WizardState) {
  if (typeof window === 'undefined') return
  // Never persist the secret token
  const safe: WizardState = {
    ...state,
    step2: { ...state.step2, githubToken: '' },
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(safe))
}

function clear() {
  if (typeof window !== 'undefined') localStorage.removeItem(STORAGE_KEY)
}

// Singleton reactive state shared across all composable usages on the page.
const state = ref<WizardState>(defaultState())
let hydrated = false

export function useKgSetupWizard() {
  if (!hydrated) {
    state.value = load()
    hydrated = true
  }

  function persist() {
    save(state.value)
  }

  function goTo(step: 1 | 2 | 3) {
    state.value.step = step
    persist()
  }

  function reset() {
    clear()
    state.value = defaultState()
    hydrated = false
  }

  return { state, goTo, persist, reset }
}
