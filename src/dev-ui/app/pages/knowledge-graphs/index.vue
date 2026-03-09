<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Share2, Plus, Trash2, Loader2, Building2, ChevronRight,
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
import type { KnowledgeGraphResponse, WorkspaceResponse } from '~/types'

const { listKnowledgeGraphs, createKnowledgeGraph, deleteKnowledgeGraph } = useManagementApi()
const { listWorkspaces } = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const selectedWorkspaceId = ref<string>('')
const kgs = ref<KnowledgeGraphResponse[]>([])
const loading = ref(false)
const workspacesLoading = ref(false)

// Create dialog
const showCreateDialog = ref(false)
const createName = ref('')
const createDescription = ref('')
const creating = ref(false)

// Delete dialog
const showDeleteDialog = ref(false)
const kgToDelete = ref<KnowledgeGraphResponse | null>(null)
const deleting = ref(false)

// ── Computed ───────────────────────────────────────────────────────────────

const selectedWorkspace = computed(() =>
  workspaces.value.find(w => w.id === selectedWorkspaceId.value),
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
  loading.value = true
  try {
    kgs.value = await listKnowledgeGraphs(selectedWorkspaceId.value)
  } catch (err) {
    toast.error('Failed to load knowledge graphs', { description: extractErrorMessage(err) })
    kgs.value = []
  } finally {
    loading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createName.value = ''
  createDescription.value = ''
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!createName.value.trim() || !selectedWorkspaceId.value) return
  creating.value = true
  try {
    await createKnowledgeGraph(selectedWorkspaceId.value, {
      name: createName.value.trim(),
      description: createDescription.value.trim(),
    })
    toast.success('Knowledge graph created')
    await fetchKgs()
  } catch (err) {
    toast.error('Failed to create knowledge graph', { description: extractErrorMessage(err) })
  } finally {
    showCreateDialog.value = false
    creating.value = false
  }
}

function confirmDelete(kg: KnowledgeGraphResponse) {
  kgToDelete.value = kg
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!kgToDelete.value) return
  deleting.value = true
  try {
    await deleteKnowledgeGraph(kgToDelete.value.id)
    toast.success('Knowledge graph deleted')
    await fetchKgs()
  } catch (err) {
    toast.error('Failed to delete knowledge graph', { description: extractErrorMessage(err) })
  } finally {
    showDeleteDialog.value = false
    kgToDelete.value = null
    deleting.value = false
  }
}

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    kgs.value = []
    selectedWorkspaceId.value = ''
    fetchWorkspaces()
  }
})

watch(selectedWorkspaceId, (id) => {
  if (id) fetchKgs()
  else kgs.value = []
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Share2 class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Knowledge Graphs</h1>
          <p class="text-sm text-muted-foreground">Manage per-tenant AGE knowledge graphs</p>
        </div>
      </div>
      <Button :disabled="!hasTenant || !selectedWorkspaceId" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Knowledge Graph
      </Button>
    </div>

    <Separator />

    <!-- No tenant -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view knowledge graphs.</p>
    </div>

    <template v-else>
      <!-- Workspace selector -->
      <div class="flex items-center gap-3">
        <Label class="shrink-0 text-sm text-muted-foreground">Workspace</Label>
        <div v-if="workspacesLoading" class="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading workspaces...
        </div>
        <Select v-else v-model="selectedWorkspaceId" :disabled="workspaces.length === 0">
          <SelectTrigger class="w-64">
            <SelectValue :placeholder="workspaces.length === 0 ? 'No workspaces' : 'Select workspace...'" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="ws in workspaces" :key="ws.id" :value="ws.id">
              {{ ws.name }}{{ ws.is_root ? ' (Root)' : '' }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <!-- Table -->
      <Card>
        <CardContent class="p-0">
          <!-- Loading -->
          <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading knowledge graphs...
          </div>

          <!-- No workspace selected -->
          <div v-else-if="!selectedWorkspaceId" class="py-12 text-center text-muted-foreground">
            <Share2 class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No workspace selected</h3>
            <p class="mt-1 text-sm">Select a workspace to view its knowledge graphs.</p>
          </div>

          <!-- Empty -->
          <div v-else-if="kgs.length === 0" class="py-12 text-center text-muted-foreground">
            <Share2 class="mx-auto size-12 text-muted-foreground/50" />
            <h3 class="mt-4 text-lg font-semibold">No knowledge graphs</h3>
            <p class="mt-1 text-sm">Create a knowledge graph to scope graph data per tenant.</p>
            <Button variant="outline" size="sm" class="mt-4" @click="openCreateDialog">
              <Plus class="mr-2 size-4" />
              Create Knowledge Graph
            </Button>
          </div>

          <!-- Table rows -->
          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>ID</TableHead>
                <TableHead class="w-[60px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="kg in kgs" :key="kg.id">
                <TableCell class="font-medium">{{ kg.name }}</TableCell>
                <TableCell class="text-muted-foreground">{{ kg.description || '—' }}</TableCell>
                <TableCell>
                  <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{{ kg.id }}</code>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    @click="confirmDelete(kg)"
                  >
                    <Trash2 class="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <!-- Data Sources link -->
      <div v-if="kgs.length > 0" class="flex items-center justify-end">
        <NuxtLink to="/data-sources">
          <Button variant="outline" size="sm">
            <ChevronRight class="mr-2 size-4" />
            Manage Data Sources
          </Button>
        </NuxtLink>
      </div>
    </template>

    <!-- Create dialog -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Knowledge Graph</DialogTitle>
          <DialogDescription>
            Create a new knowledge graph in workspace
            <span class="font-medium">{{ selectedWorkspace?.name }}</span>.
            Each knowledge graph gets its own AGE graph for data isolation.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-1.5">
            <Label for="kg-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="kg-name"
              v-model="createName"
              placeholder="My Knowledge Graph"
              @keydown.enter="handleCreate"
            />
          </div>
          <div class="space-y-1.5">
            <Label for="kg-description">Description</Label>
            <Input
              id="kg-description"
              v-model="createDescription"
              placeholder="Optional description"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button :disabled="creating || !createName.trim()" @click="handleCreate">
            <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete dialog -->
    <Dialog v-model:open="showDeleteDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Knowledge Graph</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{{ kgToDelete?.name }}"?
            This will delete the AGE graph and all data in it. This action cannot be undone.
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
