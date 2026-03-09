import type { SyncJobResponse } from '~/types'

/**
 * Typed API client for the Ingestion bounded context.
 *
 * Covers SyncJob listing and manual trigger.
 */
export function useIngestionApi() {
  const { apiFetch } = useApiClient()

  // ── Sync Jobs ──────────────────────────────────────────────────────────

  function listSyncJobs(
    dataSourceId: string,
    options?: { knowledgeGraphId?: string; statusFilter?: string; limit?: number },
  ): Promise<SyncJobResponse[]> {
    return apiFetch<SyncJobResponse[]>('/ingestion/sync-jobs', {
      query: {
        data_source_id: dataSourceId,
        ...(options?.knowledgeGraphId ? { knowledge_graph_id: options.knowledgeGraphId } : {}),
        ...(options?.statusFilter ? { status_filter: options.statusFilter } : {}),
        ...(options?.limit ? { limit: options.limit } : {}),
      },
    })
  }

  function getSyncJob(jobId: string): Promise<SyncJobResponse> {
    return apiFetch<SyncJobResponse>(`/ingestion/sync-jobs/${jobId}`)
  }

  function triggerSync(
    knowledgeGraphId: string,
    dataSourceId: string,
    adapterType: string,
  ): Promise<SyncJobResponse> {
    return apiFetch<SyncJobResponse>('/ingestion/sync-jobs', {
      method: 'POST',
      body: {
        knowledge_graph_id: knowledgeGraphId,
        data_source_id: dataSourceId,
        adapter_type: adapterType,
      },
    })
  }

  return {
    listSyncJobs,
    getSyncJob,
    triggerSync,
  }
}
