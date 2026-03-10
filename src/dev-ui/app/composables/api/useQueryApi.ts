import type { CypherResult } from '~/types'

/**
 * Typed API client for the Querying bounded context.
 *
 * Uses the REST endpoint POST /graph/query which accepts Bearer token
 * (JWT) authentication — the same as all other graph API endpoints.
 * The MCP endpoint at /query/mcp requires an X-API-Key and is intended
 * for external agent consumers, not the dev UI.
 */
export function useQueryApi() {
  const { apiFetch } = useApiClient()

  async function queryGraph(
    cypher: string,
    timeoutSeconds?: number,
    maxRows?: number,
    knowledgeGraphId?: string | null,
  ): Promise<CypherResult> {
    const body: Record<string, unknown> = { cypher }
    if (timeoutSeconds !== undefined) body.timeout_seconds = timeoutSeconds
    if (maxRows !== undefined) body.max_rows = maxRows
    if (knowledgeGraphId) body.knowledge_graph_id = knowledgeGraphId

    return apiFetch<CypherResult>('/graph/query', {
      method: 'POST',
      body,
    })
  }

  return { queryGraph }
}
