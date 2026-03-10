<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Wand2, ChevronRight, ChevronLeft, Check, Loader2,
  Share2, Cable, Building2, Github,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

import type { WorkspaceResponse, KnowledgeGraphResponse } from '~/types'

const router = useRouter()
const { listWorkspaces } = useIamApi()
const { createKnowledgeGraph, createDataSource } = useManagementApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const { state, goTo, persist, reset } = useKgSetupWizard()

// ── Workspaces ─────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const workspacesLoading = ref(false)

async function fetchWorkspaces() {
  workspacesLoading.value = true
  try {
    const res = await listWorkspaces()
    workspaces.value = res.workspaces
    if (res.workspaces.length > 0 && !state.value.step1.workspaceId) {
      state.value.step1.workspaceId = res.workspaces[0].id
      persist()
    }
  } catch (err) {
    toast.error('Failed to load workspaces', { description: extractErrorMessage(err) })
  } finally {
    workspacesLoading.value = false
  }
}

// ── Validation ─────────────────────────────────────────────────────────────

const step1Valid = computed(() =>
  !!state.value.step1.workspaceId && state.value.step1.kgName.trim().length > 0,
)

const step2Valid = computed(() => {
  const s2 = state.value.step2
  if (!s2.dsName.trim()) return false
  if (s2.adapterType === 'github') {
    return s2.github.owner.trim().length > 0 && s2.github.repo.trim().length > 0
  }
  return true
})

// ── Submit ─────────────────────────────────────────────────────────────────

const submitting = ref(false)
const createdKg = ref<KnowledgeGraphResponse | null>(null)

async function handleSubmit() {
  submitting.value = true
  try {
    // Step 1: create the Knowledge Graph
    const kg = await createKnowledgeGraph(state.value.step1.workspaceId, {
      name: state.value.step1.kgName.trim(),
      description: state.value.step1.kgDescription.trim(),
    })
    createdKg.value = kg

    // Step 2: create the Data Source
    const s2 = state.value.step2
    const connectionConfig = buildConnectionConfig()
    const credentials = buildCredentials()

    await createDataSource(kg.id, {
      name: s2.dsName.trim(),
      adapter_type: s2.adapterType,
      connection_config: connectionConfig,
      credentials: credentials ?? undefined,
    })

    toast.success('Knowledge Graph and Data Source created!', {
      description: `"${kg.name}" is ready. The first sync will begin shortly.`,
    })
    reset()
    router.push('/knowledge-graphs')
  } catch (err) {
    toast.error('Setup failed', { description: extractErrorMessage(err) })
  } finally {
    submitting.value = false
  }
}

function buildConnectionConfig(): Record<string, string> {
  const s2 = state.value.step2
  if (s2.adapterType === 'github') {
    const cfg: Record<string, string> = {
      owner: s2.github.owner.trim(),
      repo: s2.github.repo.trim(),
    }
    if (s2.github.branch.trim() && s2.github.branch.trim() !== 'main') {
      cfg.branch = s2.github.branch.trim()
    }
    return cfg
  }
  return {}
}

function buildCredentials(): Record<string, string> | null {
  const s2 = state.value.step2
  if (s2.adapterType === 'github' && s2.githubToken.trim()) {
    return { token: s2.githubToken.trim() }
  }
  return null
}

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    state.value.step1.workspaceId = ''
    fetchWorkspaces()
  }
})

// Persist on every change
watch(state, persist, { deep: true })

// ── Step metadata ──────────────────────────────────────────────────────────

const steps = [
  { number: 1, label: 'Knowledge Graph', description: 'Name and locate your graph' },
  { number: 2, label: 'Data Source', description: 'Connect an adapter' },
  { number: 3, label: 'Review', description: 'Confirm and create' },
]

const selectedWorkspaceName = computed(
  () => workspaces.value.find(w => w.id === state.value.step1.workspaceId)?.name ?? '',
)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <Wand2 class="size-6 text-muted-foreground" />
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Setup Wizard</h1>
        <p class="text-sm text-muted-foreground">Create a Knowledge Graph and connect your first data source</p>
      </div>
    </div>

    <Separator />

    <!-- No tenant -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to use the setup wizard.</p>
    </div>

    <template v-else>
      <!-- Stepper header -->
      <div class="flex items-center gap-0">
        <template v-for="(step, idx) in steps" :key="step.number">
          <button
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
            :class="{
              'text-primary font-medium': state.step === step.number,
              'text-muted-foreground': state.step !== step.number,
              'cursor-pointer hover:text-foreground': step.number < state.step,
              'cursor-default': step.number >= state.step,
            }"
            :disabled="step.number > state.step"
            @click="step.number < state.step ? goTo(step.number as 1|2|3) : undefined"
          >
            <span
              class="flex size-6 items-center justify-center rounded-full text-xs font-bold shrink-0"
              :class="{
                'bg-primary text-primary-foreground': state.step === step.number,
                'bg-green-600 text-white': step.number < state.step,
                'bg-muted text-muted-foreground': step.number > state.step,
              }"
            >
              <Check v-if="step.number < state.step" class="size-3.5" />
              <span v-else>{{ step.number }}</span>
            </span>
            <span class="hidden sm:block">{{ step.label }}</span>
          </button>
          <ChevronRight v-if="idx < steps.length - 1" class="size-4 shrink-0 text-muted-foreground" />
        </template>
      </div>

      <!-- ── Step 1: Knowledge Graph ── -->
      <Card v-if="state.step === 1">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Share2 class="size-4" />
            Name your Knowledge Graph
          </CardTitle>
          <CardDescription>
            A Knowledge Graph scopes all your data and queries within a tenant workspace.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- Workspace -->
          <div class="space-y-1.5">
            <Label>Workspace <span class="text-destructive">*</span></Label>
            <div v-if="workspacesLoading" class="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 class="size-4 animate-spin" />Loading workspaces...
            </div>
            <Select
              v-else
              v-model="state.step1.workspaceId"
              :disabled="workspaces.length === 0"
            >
              <SelectTrigger class="w-full max-w-sm">
                <SelectValue :placeholder="workspaces.length === 0 ? 'No workspaces available' : 'Select a workspace...'" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="ws in workspaces" :key="ws.id" :value="ws.id">
                  {{ ws.name }}{{ ws.is_root ? ' (Root)' : '' }}
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="text-xs text-muted-foreground">
              Workspaces organize resources within your tenant.
            </p>
          </div>

          <!-- KG Name -->
          <div class="space-y-1.5">
            <Label for="kg-name">Knowledge Graph Name <span class="text-destructive">*</span></Label>
            <Input
              id="kg-name"
              v-model="state.step1.kgName"
              placeholder="e.g. Production Engineering Docs"
              class="max-w-sm"
              @keydown.enter="step1Valid && goTo(2)"
            />
          </div>

          <!-- KG Description -->
          <div class="space-y-1.5">
            <Label for="kg-desc">Description <span class="text-muted-foreground text-xs">(optional)</span></Label>
            <Input
              id="kg-desc"
              v-model="state.step1.kgDescription"
              placeholder="What does this knowledge graph contain?"
              class="max-w-sm"
            />
          </div>

          <!-- Navigation -->
          <div class="flex items-center justify-between pt-2">
            <NuxtLink to="/knowledge-graphs">
              <Button variant="ghost" size="sm">Cancel</Button>
            </NuxtLink>
            <Button :disabled="!step1Valid" @click="goTo(2)">
              Next: Add Data Source
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- ── Step 2: Data Source ── -->
      <Card v-if="state.step === 2">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Cable class="size-4" />
            Connect a Data Source
          </CardTitle>
          <CardDescription>
            A data source pulls content from an external system into your Knowledge Graph.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- DS Name -->
          <div class="space-y-1.5">
            <Label for="ds-name">Data Source Name <span class="text-destructive">*</span></Label>
            <Input
              id="ds-name"
              v-model="state.step2.dsName"
              placeholder="e.g. Platform Engineering Repo"
              class="max-w-sm"
            />
          </div>

          <!-- Adapter Type -->
          <div class="space-y-1.5">
            <Label>Adapter Type <span class="text-destructive">*</span></Label>
            <Select v-model="state.step2.adapterType">
              <SelectTrigger class="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="github">
                  <span class="flex items-center gap-2">
                    <Github class="size-3.5" />
                    GitHub
                  </span>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- GitHub adapter fields -->
          <template v-if="state.step2.adapterType === 'github'">
            <div class="rounded-lg border bg-muted/30 p-4 space-y-4">
              <p class="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                <Github class="size-4" />
                GitHub Connection
              </p>

              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div class="space-y-1.5">
                  <Label for="gh-owner">Organization / User <span class="text-destructive">*</span></Label>
                  <Input
                    id="gh-owner"
                    v-model="state.step2.github.owner"
                    placeholder="my-org"
                  />
                  <p class="text-xs text-muted-foreground">The GitHub org or personal account name</p>
                </div>

                <div class="space-y-1.5">
                  <Label for="gh-repo">Repository <span class="text-destructive">*</span></Label>
                  <Input
                    id="gh-repo"
                    v-model="state.step2.github.repo"
                    placeholder="my-repo"
                  />
                  <p class="text-xs text-muted-foreground">Repository name (without the owner prefix)</p>
                </div>
              </div>

              <div class="space-y-1.5">
                <Label for="gh-branch">Branch</Label>
                <Input
                  id="gh-branch"
                  v-model="state.step2.github.branch"
                  placeholder="main"
                  class="max-w-48"
                />
                <p class="text-xs text-muted-foreground">Branch to index. Defaults to <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs">main</code>.</p>
              </div>

              <div class="space-y-1.5">
                <Label for="gh-token">
                  Personal Access Token
                  <Badge variant="secondary" class="ml-1.5 text-xs">encrypted</Badge>
                </Label>
                <Input
                  id="gh-token"
                  v-model="state.step2.githubToken"
                  type="password"
                  placeholder="ghp_..."
                  class="max-w-sm font-mono"
                />
                <p class="text-xs text-muted-foreground">
                  Required for private repos. Stored encrypted at rest — never returned by the API.
                  Leave empty for public repositories.
                </p>
              </div>
            </div>
          </template>

          <!-- Navigation -->
          <div class="flex items-center justify-between pt-2">
            <Button variant="outline" @click="goTo(1)">
              <ChevronLeft class="mr-1 size-4" />
              Back
            </Button>
            <Button :disabled="!step2Valid" @click="goTo(3)">
              Review Setup
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- ── Step 3: Review ── -->
      <Card v-if="state.step === 3">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Check class="size-4" />
            Review and Create
          </CardTitle>
          <CardDescription>
            Confirm your setup before creating resources.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-6">
          <!-- KG Summary -->
          <div class="space-y-2">
            <p class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Knowledge Graph</p>
            <div class="rounded-lg border bg-muted/20 p-4 space-y-2">
              <div class="flex items-center gap-2">
                <Share2 class="size-4 text-muted-foreground shrink-0" />
                <span class="font-medium">{{ state.step1.kgName }}</span>
              </div>
              <div v-if="state.step1.kgDescription" class="text-sm text-muted-foreground pl-6">
                {{ state.step1.kgDescription }}
              </div>
              <div class="text-xs text-muted-foreground pl-6">
                Workspace: <span class="font-medium text-foreground">{{ selectedWorkspaceName }}</span>
              </div>
            </div>
          </div>

          <!-- DS Summary -->
          <div class="space-y-2">
            <p class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Data Source</p>
            <div class="rounded-lg border bg-muted/20 p-4 space-y-2">
              <div class="flex items-center gap-2">
                <Cable class="size-4 text-muted-foreground shrink-0" />
                <span class="font-medium">{{ state.step2.dsName }}</span>
                <Badge variant="secondary">{{ state.step2.adapterType }}</Badge>
              </div>
              <template v-if="state.step2.adapterType === 'github'">
                <div class="pl-6 space-y-1 text-sm">
                  <div>
                    <span class="text-muted-foreground">Repository: </span>
                    <span class="font-mono font-medium">{{ state.step2.github.owner }}/{{ state.step2.github.repo }}</span>
                  </div>
                  <div>
                    <span class="text-muted-foreground">Branch: </span>
                    <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs">{{ state.step2.github.branch || 'main' }}</code>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <span class="text-muted-foreground">Credentials: </span>
                    <span v-if="state.step2.githubToken" class="text-green-600 dark:text-green-400 text-xs font-medium">Token provided (encrypted)</span>
                    <span v-else class="text-muted-foreground text-xs">None (public repo)</span>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- Navigation -->
          <div class="flex items-center justify-between pt-2">
            <Button variant="outline" @click="goTo(2)">
              <ChevronLeft class="mr-1 size-4" />
              Back
            </Button>
            <Button :disabled="submitting" @click="handleSubmit">
              <Loader2 v-if="submitting" class="mr-2 size-4 animate-spin" />
              <Check v-else class="mr-2 size-4" />
              Create and Start Sync
            </Button>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
