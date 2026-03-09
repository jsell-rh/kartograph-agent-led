<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  LayoutDashboard,
  Database,
  Share2,
  Terminal,
  KeyRound,
  Plug,
  FolderTree,
  Building2,
  ArrowRight,
  CheckCircle2,
  Circle,
  X,
  Loader2,
  Layers,
  Plus,
} from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

import type {
  SchemaLabelsResponse,
  APIKeyResponse,
  WorkspaceListResponse,
  KnowledgeGraphResponse,
  DataSourceResponse,
} from '~/types'

const { listNodeLabels, listEdgeLabels } = useGraphApi()
const { listApiKeys, listWorkspaces } = useIamApi()
const { listKnowledgeGraphs, listDataSources } = useManagementApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, currentTenantName, tenantVersion } = useTenant()

// ── Stats state ──────────────────────────────────────────────────────────

const statsLoading = ref(false)
const nodeTypeCount = ref<number | null>(null)
const edgeTypeCount = ref<number | null>(null)
const apiKeyCount = ref<number | null>(null)
const workspaceCount = ref<number | null>(null)
const kgCount = ref<number | null>(null)
const dsCount = ref<number | null>(null)
const apiKeys = ref<APIKeyResponse[]>([])

// ── Onboarding state ─────────────────────────────────────────────────────

const ONBOARDING_KEY = 'kartograph:onboarding-dismissed'

const onboardingDismissed = ref(false)

function loadOnboardingState() {
  if (typeof window !== 'undefined') {
    onboardingDismissed.value = localStorage.getItem(ONBOARDING_KEY) === 'true'
  }
}

function dismissOnboarding() {
  onboardingDismissed.value = true
  if (typeof window !== 'undefined') {
    localStorage.setItem(ONBOARDING_KEY, 'true')
  }
}

// ── Checklist computed ───────────────────────────────────────────────────

const checklistItems = computed(() => [
  {
    done: hasTenant.value,
    label: 'Create a tenant',
    description: 'You need a tenant to organize your knowledge graphs.',
    actionTo: '/tenants',
    actionLabel: 'Manage Tenants',
  },
  {
    done: (kgCount.value ?? 0) > 0,
    label: 'Create a Knowledge Graph',
    description: 'Set up a knowledge graph to store and query your data.',
    actionTo: '/knowledge-graphs',
    actionLabel: 'Create KG',
  },
  {
    done: (dsCount.value ?? 0) > 0,
    label: 'Connect a Data Source',
    description: 'Add a data source to ingest data into your knowledge graph.',
    actionTo: '/data-sources',
    actionLabel: 'Add Data Source',
  },
  {
    done: (apiKeyCount.value ?? 0) > 0,
    label: 'Create an API key',
    description: 'Generate an API key for programmatic access.',
    actionTo: '/api-keys',
    actionLabel: 'Create API Key',
  },
  {
    done: apiKeys.value.some((k) => k.last_used_at !== null),
    label: 'Connect via MCP',
    description: 'Use your API key to connect an AI agent via MCP.',
    actionTo: '/integrate/mcp',
    actionLabel: 'MCP Integration',
  },
])

const allChecklistDone = computed(() => checklistItems.value.every((item) => item.done))
const completedCount = computed(() => checklistItems.value.filter((item) => item.done).length)

const showChecklist = computed(() => {
  if (onboardingDismissed.value) return false
  return !allChecklistDone.value
})

// ── Stats cards config ───────────────────────────────────────────────────

const primaryStatsCards = computed(() => [
  {
    label: 'Knowledge Graphs',
    count: kgCount.value,
    icon: Layers,
    to: '/knowledge-graphs',
  },
  {
    label: 'Data Sources',
    count: dsCount.value,
    icon: Database,
    to: '/data-sources',
  },
  {
    label: 'API Keys',
    count: apiKeyCount.value,
    icon: KeyRound,
    to: '/api-keys',
  },
  {
    label: 'Workspaces',
    count: workspaceCount.value,
    icon: FolderTree,
    to: '/workspaces',
  },
])

const schemaStatsCards = computed(() => [
  {
    label: 'Node Types',
    count: nodeTypeCount.value,
    icon: Share2,
    to: '/graph/schema',
  },
  {
    label: 'Edge Types',
    count: edgeTypeCount.value,
    icon: Share2,
    to: '/graph/schema',
  },
])

// ── Quick actions config ─────────────────────────────────────────────────

const quickActions = computed(() => [
  {
    title: 'New Knowledge Graph',
    description: 'Create a knowledge graph to scope graph data per tenant',
    icon: Layers,
    to: '/knowledge-graphs',
    highlight: (kgCount.value ?? 0) === 0,
  },
  {
    title: 'Add Data Source',
    description: 'Connect a GitHub, Confluence, or custom data source',
    icon: Database,
    to: '/data-sources',
    highlight: (kgCount.value ?? 0) > 0 && (dsCount.value ?? 0) === 0,
  },
  {
    title: 'Run Query',
    description: 'Execute Cypher queries against the graph',
    icon: Terminal,
    to: '/query',
    highlight: false,
  },
  {
    title: 'Browse Schema',
    description: 'Explore node and edge type definitions',
    icon: Share2,
    to: '/graph/schema',
    highlight: false,
  },
  {
    title: 'Create API Key',
    description: 'Generate keys for programmatic access',
    icon: KeyRound,
    to: '/api-keys',
    highlight: false,
  },
  {
    title: 'MCP Integration',
    description: 'Connect AI agents via Model Context Protocol',
    icon: Plug,
    to: '/integrate/mcp',
    highlight: false,
  },
])

// ── Data fetching ────────────────────────────────────────────────────────

async function fetchStats() {
  if (!hasTenant.value) return
  statsLoading.value = true

  // Fetch IAM stats and graph schema in parallel
  const [keysResult, wsResult, nodeResult, edgeResult] = await Promise.allSettled([
    listApiKeys(),
    listWorkspaces(),
    listNodeLabels(),
    listEdgeLabels(),
  ])

  if (keysResult.status === 'fulfilled') {
    const keys = keysResult.value as APIKeyResponse[]
    apiKeys.value = keys
    apiKeyCount.value = keys.filter((k) => !k.is_revoked).length
  } else {
    apiKeys.value = []
    apiKeyCount.value = null
  }

  nodeTypeCount.value = nodeResult.status === 'fulfilled'
    ? (nodeResult.value as SchemaLabelsResponse).count
    : null
  edgeTypeCount.value = edgeResult.status === 'fulfilled'
    ? (edgeResult.value as SchemaLabelsResponse).count
    : null

  let wsIds: string[] = []
  if (wsResult.status === 'fulfilled') {
    const res = wsResult.value as WorkspaceListResponse
    workspaceCount.value = res.count
    wsIds = res.workspaces.map((ws) => ws.id)
  } else {
    workspaceCount.value = null
  }

  // Fetch all KGs across all workspaces in parallel
  if (wsIds.length > 0) {
    const kgResults = await Promise.allSettled(
      wsIds.map((wsId) => listKnowledgeGraphs(wsId)),
    )
    const allKgs: KnowledgeGraphResponse[] = []
    for (const r of kgResults) {
      if (r.status === 'fulfilled') {
        allKgs.push(...(r.value as KnowledgeGraphResponse[]))
      }
    }
    kgCount.value = allKgs.length

    // Fetch all data sources across all KGs in parallel
    if (allKgs.length > 0) {
      const dsResults = await Promise.allSettled(
        allKgs.map((kg) => listDataSources(kg.id)),
      )
      let total = 0
      for (const r of dsResults) {
        if (r.status === 'fulfilled') {
          total += (r.value as DataSourceResponse[]).length
        }
      }
      dsCount.value = total
    } else {
      dsCount.value = 0
    }
  } else {
    kgCount.value = 0
    dsCount.value = 0
  }

  statsLoading.value = false
}

onMounted(() => {
  loadOnboardingState()
  if (hasTenant.value) fetchStats()
})

watch(tenantVersion, () => {
  if (hasTenant.value) fetchStats()
})
</script>

<template>
  <div class="space-y-8">
    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to get started.</p>
    </div>

    <template v-else>
      <!-- A. Welcome Header -->
      <div>
        <div class="flex items-center gap-3">
          <LayoutDashboard class="size-6 text-muted-foreground" />
          <div>
            <h1 class="text-2xl font-bold tracking-tight">
              Welcome to Kartograph
            </h1>
            <p class="text-sm text-muted-foreground">
              Knowledge graph platform
              <span v-if="currentTenantName"> — {{ currentTenantName }}</span>
            </p>
          </div>
        </div>
      </div>

      <Separator />

      <!-- B. Primary Stats: KGs, Data Sources, API Keys, Workspaces -->
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <NuxtLink
          v-for="stat in primaryStatsCards"
          :key="stat.label"
          :to="stat.to"
          class="group"
        >
          <Card class="transition-colors group-hover:border-primary/30">
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <component :is="stat.icon" class="size-4 text-muted-foreground" />
              </div>
              <div class="min-w-0">
                <div class="text-2xl font-bold tracking-tight">
                  <template v-if="statsLoading">
                    <Loader2 class="size-5 animate-spin text-muted-foreground" />
                  </template>
                  <template v-else>
                    {{ stat.count !== null ? stat.count : '—' }}
                  </template>
                </div>
                <p class="text-xs text-muted-foreground truncate">{{ stat.label }}</p>
              </div>
            </CardContent>
          </Card>
        </NuxtLink>
      </div>

      <!-- C. Graph Schema Stats: Node Types, Edge Types -->
      <div class="grid grid-cols-2 gap-4">
        <NuxtLink
          v-for="stat in schemaStatsCards"
          :key="stat.label"
          :to="stat.to"
          class="group"
        >
          <Card class="transition-colors group-hover:border-primary/30">
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <component :is="stat.icon" class="size-4 text-muted-foreground" />
              </div>
              <div class="min-w-0">
                <div class="text-2xl font-bold tracking-tight">
                  <template v-if="statsLoading">
                    <Loader2 class="size-5 animate-spin text-muted-foreground" />
                  </template>
                  <template v-else>
                    {{ stat.count !== null ? stat.count : '—' }}
                  </template>
                </div>
                <p class="text-xs text-muted-foreground truncate">{{ stat.label }}</p>
              </div>
            </CardContent>
          </Card>
        </NuxtLink>
      </div>

      <!-- D. Empty State CTA — shown when no KGs exist -->
      <Card v-if="!statsLoading && kgCount === 0" class="border-dashed">
        <CardContent class="flex flex-col items-center gap-4 py-12 text-center">
          <div class="rounded-full bg-muted p-4">
            <Layers class="size-8 text-muted-foreground" />
          </div>
          <div>
            <h2 class="text-lg font-semibold">No knowledge graphs yet</h2>
            <p class="mt-1 max-w-sm mx-auto text-sm text-muted-foreground">
              Create your first knowledge graph to start ingesting data and running queries.
            </p>
          </div>
          <NuxtLink to="/knowledge-graphs">
            <Button>
              <Plus class="mr-2 size-4" />
              Create your first Knowledge Graph
            </Button>
          </NuxtLink>
        </CardContent>
      </Card>

      <!-- E. Getting Started Checklist -->
      <Card v-if="showChecklist">
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-3">
          <div>
            <CardTitle class="text-base">Getting Started</CardTitle>
            <CardDescription>
              {{ completedCount }} of {{ checklistItems.length }} completed
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" class="size-8" @click="dismissOnboarding">
            <X class="size-4" />
          </Button>
        </CardHeader>
        <CardContent class="space-y-3">
          <!-- Progress bar -->
          <div class="h-1.5 w-full rounded-full bg-muted">
            <div
              class="h-1.5 rounded-full bg-primary transition-all"
              :style="{ width: `${(completedCount / checklistItems.length) * 100}%` }"
            />
          </div>

          <div class="space-y-2">
            <div
              v-for="item in checklistItems"
              :key="item.label"
              class="flex items-start gap-3 rounded-md p-2"
              :class="item.done ? 'opacity-60' : ''"
            >
              <CheckCircle2 v-if="item.done" class="mt-0.5 size-4 shrink-0 text-green-600" />
              <Circle v-else class="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium" :class="item.done ? 'line-through' : ''">
                  {{ item.label }}
                </p>
                <p class="text-xs text-muted-foreground">{{ item.description }}</p>
              </div>
              <NuxtLink v-if="!item.done" :to="item.actionTo">
                <Button variant="ghost" size="sm" class="h-7 text-xs">
                  {{ item.actionLabel }}
                  <ArrowRight class="ml-1 size-3" />
                </Button>
              </NuxtLink>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- F. Quick Actions Grid -->
      <div>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Quick Actions
        </h2>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <NuxtLink
            v-for="action in quickActions"
            :key="action.title"
            :to="action.to"
            class="group"
          >
            <Card
              class="h-full transition-colors group-hover:border-primary/30"
              :class="action.highlight ? 'border-primary/30 bg-primary/5' : ''"
            >
              <CardContent class="flex items-start gap-3 p-4">
                <div class="rounded-md bg-muted p-2">
                  <component :is="action.icon" class="size-4 text-muted-foreground" />
                </div>
                <div class="min-w-0">
                  <p class="text-sm font-medium transition-colors group-hover:text-primary">
                    {{ action.title }}
                  </p>
                  <p class="text-xs text-muted-foreground">{{ action.description }}</p>
                </div>
              </CardContent>
            </Card>
          </NuxtLink>
        </div>
      </div>
    </template>
  </div>
</template>
