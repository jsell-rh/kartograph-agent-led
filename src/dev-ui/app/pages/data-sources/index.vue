<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable, Plus, Trash2, Loader2, Building2, ShieldCheck, ShieldOff, Eye, EyeOff, Info, Layers,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
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
import type { DataSourceResponse } from '~/types'
import {
  validateGitHubAdapter,
  hasGitHubErrors,
  buildGitHubConnectionConfig,
  buildGitHubCredentials,
} from '~/utils/data-source-forms'

const { listDataSources, createDataSource, deleteDataSource } = useManagementApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const { currentKgId, currentKg, kgVersion } = useCurrentKg()

const ADAPTER_TYPES = ['github'] as const

// ── State ──────────────────────────────────────────────────────────────────

const dataSources = ref<DataSourceResponse[]>([])
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

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchDataSources() {
  if (!currentKgId.value) return
  loading.value = true
  try {
    dataSources.value = await listDataSources(currentKgId.value)
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
  if (!createName.value.trim() || !currentKgId.value) return

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
    await createDataSource(currentKgId.value!, {
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
  if (hasTenant.value && currentKgId.value) fetchDataSources()
})

watch([tenantVersion, kgVersion], () => {
  dataSources.value = []
  if (hasTenant.value && currentKgId.value) fetchDataSources()
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
      <Button :disabled="!hasTenant || !currentKgId" @click="openCreateDialog">
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
      <!-- Active KG indicator -->
      <div v-if="currentKg" class="flex items-center gap-2 text-sm text-muted-foreground">
        <Layers class="size-4 shrink-0" />
        <span>Knowledge Graph: <span class="font-medium text-foreground">{{ currentKg.name }}</span></span>
        <NuxtLink to="/knowledge-graphs" class="ml-auto text-xs hover:text-primary underline-offset-2 hover:underline">Switch KG</NuxtLink>
      </div>

      <!-- Table -->
      <Card>
        <CardContent class="p-0">
          <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading data sources...
          </div>

          <div v-else-if="!currentKgId" class="py-12 text-center text-muted-foreground">
            <Cable class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No knowledge graph selected</h3>
            <p class="mt-1 text-sm">Select a knowledge graph from the sidebar to view data sources.</p>
            <NuxtLink to="/knowledge-graphs">
              <Button variant="outline" size="sm" class="mt-4">Go to Knowledge Graphs</Button>
            </NuxtLink>
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
            <span class="font-medium">{{ currentKg?.name }}</span>.
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
