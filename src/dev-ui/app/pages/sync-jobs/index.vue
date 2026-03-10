<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  RefreshCw, Play, Loader2, Building2, Cable, CheckCircle2, XCircle,
  Clock, Activity, ChevronDown, ChevronUp, Layers,
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
import type { DataSourceResponse, SyncJobResponse } from '~/types'

const { listDataSources } = useManagementApi()
const { listSyncJobs, triggerSync } = useIngestionApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()
const { currentKgId, currentKg, kgVersion } = useCurrentKg()

// ── State ──────────────────────────────────────────────────────────────────

const dataSources = ref<DataSourceResponse[]>([])
const selectedDsId = ref<string>('')
const syncJobs = ref<SyncJobResponse[]>([])

const dsLoading = ref(false)
const jobsLoading = ref(false)
const triggering = ref(false)

const expandedJobId = ref<string | null>(null)

// Auto-refresh interval (5s when there are running/pending jobs)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// ── Computed ───────────────────────────────────────────────────────────────

const selectedDs = computed(() =>
  dataSources.value.find(d => d.id === selectedDsId.value),
)

const hasLiveJobs = computed(() =>
  syncJobs.value.some(j => j.status === 'running' || j.status === 'pending'),
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

async function fetchDataSources() {
  if (!currentKgId.value) return
  dsLoading.value = true
  try {
    dataSources.value = await listDataSources(currentKgId.value)
    const first = dataSources.value[0]
    if (first && !selectedDsId.value) {
      selectedDsId.value = first.id
    }
  } catch (err) {
    toast.error('Failed to load data sources', { description: extractErrorMessage(err) })
    dataSources.value = []
  } finally {
    dsLoading.value = false
  }
}

async function fetchSyncJobs(silent = false) {
  if (!selectedDsId.value) return
  if (!silent) jobsLoading.value = true
  try {
    syncJobs.value = await listSyncJobs(selectedDsId.value, {
      knowledgeGraphId: currentKgId.value || undefined,
    })
  } catch (err) {
    if (!silent) toast.error('Failed to load sync jobs', { description: extractErrorMessage(err) })
    if (!silent) syncJobs.value = []
  } finally {
    if (!silent) jobsLoading.value = false
  }
}

// ── Auto-refresh ────────────────────────────────────────────────────────────

function startAutoRefresh() {
  if (refreshTimer) return
  refreshTimer = setInterval(() => {
    if (hasLiveJobs.value) fetchSyncJobs(true)
  }, 5000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

async function handleTrigger() {
  if (!selectedDs.value || !currentKgId.value) return
  triggering.value = true
  try {
    const job = await triggerSync(
      currentKgId.value,
      selectedDs.value.id,
      selectedDs.value.adapter_type,
    )
    toast.success('Sync job triggered', { description: `Job ${job.id} is now PENDING` })
    await fetchSyncJobs()
    startAutoRefresh()
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
  if (hasTenant.value && currentKgId.value) fetchDataSources()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})

watch([tenantVersion, kgVersion], () => {
  dataSources.value = []
  selectedDsId.value = ''
  syncJobs.value = []
  if (hasTenant.value && currentKgId.value) fetchDataSources()
})

watch(selectedDsId, (id) => {
  syncJobs.value = []
  if (id) {
    fetchSyncJobs()
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

// Stop auto-refresh when no more live jobs
watch(hasLiveJobs, (live) => {
  if (!live) stopAutoRefresh()
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
        <Button variant="outline" size="sm" :disabled="!selectedDsId || jobsLoading" @click="() => fetchSyncJobs()">
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
      <!-- Context row: KG + Data Source selector -->
      <div class="flex flex-wrap items-center gap-4">
        <!-- Active KG indicator -->
        <div v-if="currentKg" class="flex items-center gap-2 text-sm text-muted-foreground">
          <Layers class="size-4 shrink-0" />
          <span>KG: <span class="font-medium text-foreground">{{ currentKg.name }}</span></span>
        </div>
        <div v-else class="flex items-center gap-2 text-sm text-muted-foreground">
          <Layers class="size-4 shrink-0" />
          <NuxtLink to="/knowledge-graphs" class="text-xs text-primary hover:underline">Select a Knowledge Graph</NuxtLink>
        </div>

        <!-- Data Source selector -->
        <div class="flex items-center gap-2">
          <Label class="shrink-0 text-sm text-muted-foreground">Data Source</Label>
          <div v-if="dsLoading" class="flex items-center gap-1 text-sm text-muted-foreground">
            <Loader2 class="size-3.5 animate-spin" />Loading...
          </div>
          <Select v-else v-model="selectedDsId" :disabled="!currentKgId || dataSources.length === 0">
            <SelectTrigger class="w-48">
              <SelectValue :placeholder="!currentKgId ? 'Select KG first' : dataSources.length === 0 ? 'No data sources' : 'Select...'" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="ds in dataSources" :key="ds.id" :value="ds.id">
                {{ ds.name }}
                <span class="ml-1 text-xs text-muted-foreground">({{ ds.adapter_type }})</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Auto-refresh indicator -->
        <div v-if="hasLiveJobs" class="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          <div class="size-2 animate-pulse rounded-full bg-green-500" />
          Auto-refreshing
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
            <p class="mt-1 text-sm">Select a data source above to view its sync jobs.</p>
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
