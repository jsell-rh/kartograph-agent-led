import type { KnowledgeGraphResponse, DataSourceResponse } from '~/types'

/**
 * Typed API client for the Management bounded context.
 *
 * Covers KnowledgeGraphs and DataSources CRUD.
 */
export function useManagementApi() {
  const { apiFetch } = useApiClient()

  // ── Knowledge Graphs ───────────────────────────────────────────────────

  function listKnowledgeGraphs(workspaceId: string): Promise<KnowledgeGraphResponse[]> {
    return apiFetch<KnowledgeGraphResponse[]>('/management/knowledge-graphs', {
      query: { workspace_id: workspaceId },
    })
  }

  function createKnowledgeGraph(
    workspaceId: string,
    data: { name: string; description?: string },
  ): Promise<KnowledgeGraphResponse> {
    return apiFetch<KnowledgeGraphResponse>('/management/knowledge-graphs', {
      method: 'POST',
      query: { workspace_id: workspaceId },
      body: { name: data.name, description: data.description ?? '' },
    })
  }

  function deleteKnowledgeGraph(kgId: string): Promise<void> {
    return apiFetch<void>(`/management/knowledge-graphs/${kgId}`, {
      method: 'DELETE',
    })
  }

  // ── Data Sources ───────────────────────────────────────────────────────

  function listDataSources(knowledgeGraphId: string): Promise<DataSourceResponse[]> {
    return apiFetch<DataSourceResponse[]>('/management/data-sources', {
      query: { knowledge_graph_id: knowledgeGraphId },
    })
  }

  function createDataSource(
    knowledgeGraphId: string,
    data: {
      name: string
      adapter_type: string
      connection_config?: Record<string, string>
      credentials?: Record<string, string>
    },
  ): Promise<DataSourceResponse> {
    return apiFetch<DataSourceResponse>('/management/data-sources', {
      method: 'POST',
      query: { knowledge_graph_id: knowledgeGraphId },
      body: {
        name: data.name,
        adapter_type: data.adapter_type,
        connection_config: data.connection_config ?? {},
        credentials: data.credentials ?? null,
      },
    })
  }

  function deleteDataSource(dsId: string): Promise<void> {
    return apiFetch<void>(`/management/data-sources/${dsId}`, {
      method: 'DELETE',
    })
  }

  return {
    // Knowledge Graphs
    listKnowledgeGraphs,
    createKnowledgeGraph,
    deleteKnowledgeGraph,
    // Data Sources
    listDataSources,
    createDataSource,
    deleteDataSource,
  }
}
