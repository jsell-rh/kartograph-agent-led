<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  RefreshCw, Play, Loader2, Building2, Cable, CheckCircle2, XCircle,
  Clock, Activity, ChevronDown, ChevronUp,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { Card, CardContent } from '@/components/ui/card'
import type { KnowledgeGraphResponse, DataSourceResponse, SyncJobResponse, WorkspaceResponse } from '~/types'

const { listKnowledgeGraphs, listDataSources } = useManagementApi()
const { listSyncJobs, triggerSync } = useIngestionApi()
const { listWorkspaces } = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const selectedWorkspaceId = ref<string>('')
const kgs = ref<KnowledgeGraphResponse[]>([])
const selectedKgId = ref<string>('')
const dataSources = ref<DataSourceResponse[]>([])
const selectedDsId = ref<string>('')
const syncJobs = ref<SyncJobResponse[]>([])

const workspacesLoading = ref(false)
const kgsLoading = ref(false)
const dsLoading = ref(false)
const jobsLoading = ref(false)
const triggering = ref(false)

const expandedJobId = ref<string | null>(null)

// ── Computed ───────────────────────────────────────────────────────────────

const selectedDs = computed(() =>
  dataSources.value.find(d => d.id === selectedDsId.value),
)

const selectedKg = computed(() =>
  kgs.value.find(k => k.id === selectedKgId.value),
)

// ── Status helpers ─────────────────────────────────────────────────────────

type JobStatus = SyncJobResponse['status']

function statusVariant(s: JobStatus): 'secondary' | 'default' | 'outline' | 'destructive' {
  switch (s) {
    case 'completed': return 'default'
    case 'running': return 'secondary'
    case 'pending': return 'outline'
    case 'failed': return 'destructive'
  }
}

function statusIcon(s: JobStatus) {
  switch (s) {
    case 'completed': return CheckCircle2
    case 'running': return Activity
    case 'pending': return Clock
    case 'failed': return XCircle
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function duration(job: SyncJobResponse): string {
  const created = new Date(job.created_at).getTime()
  const updated = new Date(job.updated_at).getTime()
  const ms = updated - created
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`
}

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
  dsLoading.value = true
  try {
    dataSources.value = await listDataSources(selectedKgId.value)
    if (dataSources.value.length > 0 && !selectedDsId.value) {
      selectedDsId.value = dataSources.value[0].id
    }
  } catch (err) {
    toast.error('Failed to load data sources', { description: extractErrorMessage(err) })
    dataSources.value = []
  } finally {
    dsLoading.value = false
  }
}

async function fetchSyncJobs() {
  if (!selectedDsId.value) return
  jobsLoading.value = true
  try {
    syncJobs.value = await listSyncJobs(selectedDsId.value, {
      knowledgeGraphId: selectedKgId.value || undefined,
    })
  } catch (err) {
    toast.error('Failed to load sync jobs', { description: extractErrorMessage(err) })
    syncJobs.value = []
  } finally {
    jobsLoading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

async function handleTrigger() {
  if (!selectedDs.value || !selectedKgId.value) return
  triggering.value = true
  try {
    const job = await triggerSync(
      selectedKgId.value,
      selectedDs.value.id,
      selectedDs.value.adapter_type,
    )
    toast.success('Sync job triggered', { description: `Job ${job.id} is now PENDING` })
    await fetchSyncJobs()
  } catch (err) {
    toast.error('Failed to trigger sync', { description: extractErrorMessage(err) })
  } finally {
    triggering.value = false
  }
}

function toggleExpand(jobId: string) {
  expandedJobId.value = expandedJobId.value === jobId ? null : jobId
}

// ── Watchers ───────────────────────────────────────────────────────────────

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    syncJobs.value = []
    dataSources.value = []
    kgs.value = []
    workspaces.value = []
    selectedWorkspaceId.value = ''
    selectedKgId.value = ''
    selectedDsId.value = ''
    fetchWorkspaces()
  }
})

watch(selectedWorkspaceId, (id) => {
  kgs.value = []
  selectedKgId.value = ''
  dataSources.value = []
  selectedDsId.value = ''
  syncJobs.value = []
  if (id) fetchKgs()
})

watch(selectedKgId, (id) => {
  dataSources.value = []
  selectedDsId.value = ''
  syncJobs.value = []
  if (id) fetchDataSources()
})

watch(selectedDsId, (id) => {
  syncJobs.value = []
  if (id) fetchSyncJobs()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Activity class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Sync Jobs</h1>
          <p class="text-sm text-muted-foreground">View and trigger data source ingestion jobs</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="!selectedDsId || jobsLoading" @click="fetchSyncJobs">
          <RefreshCw class="mr-2 size-4" :class="{ 'animate-spin': jobsLoading }" />
          Refresh
        </Button>
        <Button :disabled="!selectedDsId || triggering" @click="handleTrigger">
          <Loader2 v-if="triggering" class="mr-2 size-4 animate-spin" />
          <Play v-else class="mr-2 size-4" />
          Trigger Sync
        </Button>
      </div>
    </div>

    <Separator />

    <!-- No tenant -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view sync jobs.</p>
    </div>

    <template v-else>
      <!-- Selectors row -->
      <div class="flex flex-wrap items-center gap-4">
        <!-- Workspace -->
        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">Workspace</Label>
          <div v-if="workspacesLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedWorkspaceId" :disabled="workspaces.length === 0">
            <SelectTrigger class="w-44">
              <SelectValue :placeholder="workspaces.length === 0 ? 'No workspaces' : 'Select...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="ws in workspaces" :key="ws.id" :value="ws.id">
                {{ ws.name }}{{ ws.is_root ? ' (Root)' : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Knowledge Graph -->
        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">KG</Label>
          <div v-if="kgsLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedKgId" :disabled="!selectedWorkspaceId || kgs.length === 0">
            <SelectTrigger class="w-44">
              <SelectValue :placeholder="!selectedWorkspaceId ? 'Select workspace first' : kgs.length === 0 ? 'No KGs' : 'Select...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="kg in kgs" :key="kg.id" :value="kg.id">
                {{ kg.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Data Source -->
        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">Data Source</Label>
          <div v-if="dsLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedDsId" :disabled="!selectedKgId || dataSources.length === 0">
            <SelectTrigger class="w-48">
              <SelectValue :placeholder="!selectedKgId ? 'Select KG first' : dataSources.length === 0 ? 'No data sources' : 'Select...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="ds in dataSources" :key="ds.id" :value="ds.id">
                {{ ds.name }}
                <span class="ml-1 text-xs text-muted-foreground">({{ ds.adapter_type }})</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <!-- Jobs table -->
      <Card>
        <CardContent class="p-0">
          <!-- Loading -->
          <div v-if="jobsLoading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading sync jobs...
          </div>

          <!-- No DS selected -->
          <div v-else-if="!selectedDsId" class="py-12 text-center text-muted-foreground">
            <Cable class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No data source selected</h3>
            <p class="mt-1 text-sm">Select a workspace, knowledge graph, and data source to view sync jobs.</p>
          </div>

          <!-- Empty -->
          <div v-else-if="syncJobs.length === 0" class="py-12 text-center text-muted-foreground">
            <Activity class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No sync jobs yet</h3>
            <p class="mt-1 text-sm">Trigger a manual sync to create the first job for this data source.</p>
            <Button variant="outline" size="sm" class="mt-4" :disabled="triggering" @click="handleTrigger">
              <Play class="mr-2 size-4" />
              Trigger Sync
            </Button>
          </div>

          <!-- Table -->
          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead class="w-[100px]">Status</TableHead>
                <TableHead>Job ID</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead class="w-[40px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <template v-for="job in syncJobs" :key="job.id">
                <TableRow
                  class="cursor-pointer"
                  @click="toggleExpand(job.id)"
                >
                  <TableCell>
                    <Badge :variant="statusVariant(job.status)" class="gap-1.5">
                      <component :is="statusIcon(job.status)" class="size-3" />
                      {{ job.status }}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{{ job.id.slice(-8) }}</code>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{{ job.adapter_type }}</Badge>
                  </TableCell>
                  <TableCell class="text-sm text-muted-foreground">
                    {{ formatDate(job.created_at) }}
                  </TableCell>
                  <TableCell class="text-sm text-muted-foreground">
                    {{ duration(job) }}
                  </TableCell>
                  <TableCell>
                    <ChevronUp v-if="expandedJobId === job.id" class="size-4 text-muted-foreground" />
                    <ChevronDown v-else class="size-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>

                <!-- Expanded row -->
                <TableRow v-if="expandedJobId === job.id" class="bg-muted/30 hover:bg-muted/30">
                  <TableCell colspan="6" class="py-4">
                    <div class="space-y-2 text-sm">
                      <div class="grid grid-cols-2 gap-x-8 gap-y-1">
                        <div>
                          <span class="text-muted-foreground">Full Job ID: </span>
                          <code class="font-mono text-xs">{{ job.id }}</code>
                        </div>
                        <div>
                          <span class="text-muted-foreground">Data Source ID: </span>
                          <code class="font-mono text-xs">{{ job.data_source_id }}</code>
                        </div>
                        <div>
                          <span class="text-muted-foreground">KG ID: </span>
                          <code class="font-mono text-xs">{{ job.knowledge_graph_id }}</code>
                        </div>
                        <div>
                          <span class="text-muted-foreground">Updated: </span>
                          <span>{{ formatDate(job.updated_at) }}</span>
                        </div>
                        <div v-if="job.job_package_id">
                          <span class="text-muted-foreground">Package ID: </span>
                          <code class="font-mono text-xs">{{ job.job_package_id }}</code>
                        </div>
                      </div>
                      <div v-if="job.error_message" class="mt-2 rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive">
                        <span class="font-medium">Error: </span>{{ job.error_message }}
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              </template>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
