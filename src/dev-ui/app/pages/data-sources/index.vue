<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable, Plus, Trash2, Loader2, Building2, ShieldCheck, ShieldOff, Eye, EyeOff, Info,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import type { KnowledgeGraphResponse, DataSourceResponse, WorkspaceResponse } from '~/types'
import {
  validateGitHubAdapter,
  hasGitHubErrors,
  buildGitHubConnectionConfig,
  buildGitHubCredentials,
} from '~/utils/data-source-forms'

const { listDataSources, createDataSource, deleteDataSource, listKnowledgeGraphs } = useManagementApi()
const { listWorkspaces } = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

const ADAPTER_TYPES = ['github'] as const

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const selectedWorkspaceId = ref<string>('')
const kgs = ref<KnowledgeGraphResponse[]>([])
const selectedKgId = ref<string>('')
const dataSources = ref<DataSourceResponse[]>([])

const workspacesLoading = ref(false)
const kgsLoading = ref(false)
const loading = ref(false)

// Create dialog
const showCreateDialog = ref(false)
const createName = ref('')
const createAdapterType = ref('github')
const creating = ref(false)

// GitHub adapter fields
const githubOwner = ref('')
const githubRepo = ref('')
const githubBranch = ref('')
const githubToken = ref('')
const githubTokenVisible = ref(false)
const githubOwnerError = ref('')
const githubRepoError = ref('')
const githubTokenError = ref('')

// Delete dialog
const showDeleteDialog = ref(false)
const dsToDelete = ref<DataSourceResponse | null>(null)
const deleting = ref(false)

// ── Computed ───────────────────────────────────────────────────────────────

const selectedKg = computed(() =>
  kgs.value.find(k => k.id === selectedKgId.value),
)

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchWorkspaces() {
  workspacesLoading.value = true
  try {
    const res = await listWorkspaces()
    workspaces.value = res.workspaces
    if (res.workspaces.length > 0 && !selectedWorkspaceId.value) {
      selectedWorkspaceId.value = res.workspaces[0].id
    }
  } catch (err) {
    toast.error('Failed to load workspaces', { description: extractErrorMessage(err) })
  } finally {
    workspacesLoading.value = false
  }
}

async function fetchKgs() {
  if (!selectedWorkspaceId.value) return
  kgsLoading.value = true
  try {
    kgs.value = await listKnowledgeGraphs(selectedWorkspaceId.value)
    if (kgs.value.length > 0 && !selectedKgId.value) {
      selectedKgId.value = kgs.value[0].id
    }
  } catch (err) {
    toast.error('Failed to load knowledge graphs', { description: extractErrorMessage(err) })
    kgs.value = []
  } finally {
    kgsLoading.value = false
  }
}

async function fetchDataSources() {
  if (!selectedKgId.value) return
  loading.value = true
  try {
    dataSources.value = await listDataSources(selectedKgId.value)
  } catch (err) {
    toast.error('Failed to load data sources', { description: extractErrorMessage(err) })
    dataSources.value = []
  } finally {
    loading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createName.value = ''
  createAdapterType.value = 'github'
  githubOwner.value = ''
  githubRepo.value = ''
  githubBranch.value = ''
  githubToken.value = ''
  githubTokenVisible.value = false
  githubOwnerError.value = ''
  githubRepoError.value = ''
  githubTokenError.value = ''
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!createName.value.trim() || !selectedKgId.value) return

  let connectionConfig: Record<string, string> = {}
  let credentials: Record<string, string> | undefined

  if (createAdapterType.value === 'github') {
    const fields = {
      owner: githubOwner.value,
      repo: githubRepo.value,
      branch: githubBranch.value,
      token: githubToken.value,
    }
    const errors = validateGitHubAdapter(fields)
    githubOwnerError.value = errors.owner
    githubRepoError.value = errors.repo
    githubTokenError.value = errors.token
    if (hasGitHubErrors(errors)) return

    connectionConfig = buildGitHubConnectionConfig(fields)
    credentials = buildGitHubCredentials(fields)
  }

  creating.value = true
  try {
    await createDataSource(selectedKgId.value, {
      name: createName.value.trim(),
      adapter_type: createAdapterType.value,
      connection_config: connectionConfig,
      credentials,
    })
    toast.success('Data source created')
    await fetchDataSources()
  } catch (err) {
    toast.error('Failed to create data source', { description: extractErrorMessage(err) })
  } finally {
    showCreateDialog.value = false
    creating.value = false
  }
}

function confirmDelete(ds: DataSourceResponse) {
  dsToDelete.value = ds
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!dsToDelete.value) return
  deleting.value = true
  try {
    await deleteDataSource(dsToDelete.value.id)
    toast.success('Data source deleted')
    await fetchDataSources()
  } catch (err) {
    toast.error('Failed to delete data source', { description: extractErrorMessage(err) })
  } finally {
    showDeleteDialog.value = false
    dsToDelete.value = null
    deleting.value = false
  }
}

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    dataSources.value = []
    kgs.value = []
    workspaces.value = []
    selectedWorkspaceId.value = ''
    selectedKgId.value = ''
    fetchWorkspaces()
  }
})

watch(selectedWorkspaceId, (id) => {
  kgs.value = []
  selectedKgId.value = ''
  dataSources.value = []
  if (id) fetchKgs()
})

watch(selectedKgId, (id) => {
  dataSources.value = []
  if (id) fetchDataSources()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Cable class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Data Sources</h1>
          <p class="text-sm text-muted-foreground">Connect data adapters to knowledge graphs</p>
        </div>
      </div>
      <Button :disabled="!hasTenant || !selectedKgId" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Add Data Source
      </Button>
    </div>

    <Separator />

    <!-- No tenant -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view data sources.</p>
    </div>

    <template v-else>
      <!-- Selectors row -->
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">Workspace</Label>
          <div v-if="workspacesLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedWorkspaceId" :disabled="workspaces.length === 0">
            <SelectTrigger class="w-52">
              <SelectValue :placeholder="workspaces.length === 0 ? 'No workspaces' : 'Select workspace...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="ws in workspaces" :key="ws.id" :value="ws.id">
                {{ ws.name }}{{ ws.is_root ? ' (Root)' : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">Knowledge Graph</Label>
          <div v-if="kgsLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedKgId" :disabled="!selectedWorkspaceId || kgs.length === 0">
            <SelectTrigger class="w-52">
              <SelectValue :placeholder="!selectedWorkspaceId ? 'Select workspace first' : kgs.length === 0 ? 'No knowledge graphs' : 'Select KG...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="kg in kgs" :key="kg.id" :value="kg.id">
                {{ kg.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <!-- Table -->
      <Card>
        <CardContent class="p-0">
          <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading data sources...
          </div>

          <div v-else-if="!selectedKgId" class="py-12 text-center text-muted-foreground">
            <Cable class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No knowledge graph selected</h3>
            <p class="mt-1 text-sm">Select a workspace and knowledge graph to view data sources.</p>
          </div>

          <div v-else-if="dataSources.length === 0" class="py-12 text-center text-muted-foreground">
            <Cable class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No data sources</h3>
            <p class="mt-1 text-sm">Add a data source to connect adapters to this knowledge graph.</p>
            <Button variant="outline" size="sm" class="mt-4" @click="openCreateDialog">
              <Plus class="mr-2 size-4" />
              Add Data Source
            </Button>
          </div>

          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Credentials</TableHead>
                <TableHead>Schedule</TableHead>
                <TableHead>ID</TableHead>
                <TableHead class="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="ds in dataSources" :key="ds.id">
                <TableCell class="font-medium">{{ ds.name }}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{{ ds.adapter_type }}</Badge>
                </TableCell>
                <TableCell>
                  <div class="flex items-center gap-1.5 text-sm">
                    <ShieldCheck v-if="ds.has_credentials" class="size-4 text-green-600 dark:text-green-400" />
                    <ShieldOff v-else class="size-4 text-muted-foreground" />
                    <span :class="ds.has_credentials ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'">
                      {{ ds.has_credentials ? 'Stored' : 'None' }}
                    </span>
                  </div>
                </TableCell>
                <TableCell class="text-sm text-muted-foreground">
                  {{ ds.schedule_type }}{{ ds.schedule_value ? ` (${ds.schedule_value})` : '' }}
                </TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{{ ds.id }}</code>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    @click="confirmDelete(ds)"
                  >
                    <Trash2 class="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </template>

    <!-- Create dialog -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Data Source</DialogTitle>
          <DialogDescription>
            Add a data source to knowledge graph
            <span class="font-medium">{{ selectedKg?.name }}</span>.
            Credentials are encrypted at rest and never returned in API responses.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-1.5">
            <Label for="ds-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="ds-name"
              v-model="createName"
              placeholder="My GitHub Source"
            />
          </div>

          <div class="space-y-1.5">
            <Label>Adapter Type <span class="text-destructive">*</span></Label>
            <Select v-model="createAdapterType">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="t in ADAPTER_TYPES" :key="t" :value="t">
                  {{ t }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- GitHub adapter fields -->
          <template v-if="createAdapterType === 'github'">
            <div class="space-y-1.5">
              <Label for="ds-gh-owner">
                GitHub Owner <span class="text-destructive">*</span>
              </Label>
              <Input
                id="ds-gh-owner"
                v-model="githubOwner"
                placeholder="my-org"
              />
              <p v-if="githubOwnerError" class="text-sm text-destructive">{{ githubOwnerError }}</p>
              <p class="text-xs text-muted-foreground">GitHub organization or username (e.g. <code>my-org</code>)</p>
            </div>

            <div class="space-y-1.5">
              <Label for="ds-gh-repo">
                Repository <span class="text-destructive">*</span>
              </Label>
              <Input
                id="ds-gh-repo"
                v-model="githubRepo"
                placeholder="my-repo"
              />
              <p v-if="githubRepoError" class="text-sm text-destructive">{{ githubRepoError }}</p>
              <p class="text-xs text-muted-foreground">Repository name without the owner prefix (e.g. <code>my-repo</code>)</p>
            </div>

            <div class="space-y-1.5">
              <Label for="ds-gh-branch">Branch</Label>
              <Input
                id="ds-gh-branch"
                v-model="githubBranch"
                placeholder="main"
              />
              <p class="text-xs text-muted-foreground">Branch to index. Defaults to the repository's default branch if empty.</p>
            </div>

            <div class="space-y-1.5">
              <div class="flex items-center gap-1.5">
                <Label for="ds-gh-token">
                  Personal Access Token <span class="text-destructive">*</span>
                </Label>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Info class="size-3.5 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent class="max-w-xs">
                    A GitHub PAT with <code>repo</code> scope (or <code>public_repo</code> for public repos).
                    Create one at GitHub → Settings → Developer settings → Personal access tokens.
                  </TooltipContent>
                </Tooltip>
              </div>
              <div class="flex gap-2">
                <Input
                  id="ds-gh-token"
                  v-model="githubToken"
                  :type="githubTokenVisible ? 'text' : 'password'"
                  placeholder="ghp_••••••••••••••••••••"
                  class="flex-1"
                />
                <button
                  type="button"
                  class="inline-flex items-center justify-center rounded-md border border-input bg-background px-2.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  :aria-label="githubTokenVisible ? 'Hide token' : 'Show token'"
                  @click="githubTokenVisible = !githubTokenVisible"
                >
                  <component :is="githubTokenVisible ? EyeOff : Eye" class="size-4" />
                </button>
              </div>
              <p v-if="githubTokenError" class="text-sm text-destructive">{{ githubTokenError }}</p>
              <Alert class="mt-1">
                <AlertDescription class="text-xs">
                  Your token is encrypted before storage and never returned by the API.
                </AlertDescription>
              </Alert>
            </div>
          </template>
        </div>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button :disabled="creating || !createName.trim()" @click="handleCreate">
            <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
            Add Data Source
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete dialog -->
    <Dialog v-model:open="showDeleteDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Data Source</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{{ dsToDelete?.name }}"?
            Any stored credentials will also be deleted. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="deleting" @click="handleDelete">
            <Loader2 v-if="deleting" class="mr-2 size-4 animate-spin" />
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
