"""Background worker that executes pending sync jobs end-to-end.

Pipeline per job:
  PENDING → RUNNING
  → GitHubAdapter.fetch_changeset() → JobPackage
  → JobPackage stored in InMemoryJobPackageStore
  → COMPLETED (with job_package_id)
  → PythonAstSyntheticExtractionAgent.extract() → MutationLog
  → _translate_mutation_log() → list[graph.MutationOperation]
  → GraphMutationService.apply_mutations()

The worker polls the ISyncJobRepository for PENDING jobs every
``poll_interval_seconds`` and processes them sequentially.

Cross-context dependencies:
  - Management: DataSourceRepository + FernetCredentialStore (via session_factory)
  - Graph: AgeGraphClient + GraphMutationService (via connection_pool — lazy import)
  - Ingestion: ISyncJobRepository + InMemoryJobPackageStore
"""

from __future__ import annotations

import asyncio
import structlog
from typing import TYPE_CHECKING

from ingestion.domain.aggregates.sync_job import SyncJob
from shared_kernel.mutation_log import MutationLog, MutationOperation

if TYPE_CHECKING:
    from graph.domain.value_objects import MutationOperation as GraphMutationOperation
    from infrastructure.database.connection_pool import ConnectionPool
    from infrastructure.settings import DatabaseSettings
    from ingestion.infrastructure.job_package_store import InMemoryJobPackageStore
    from ingestion.ports.repositories import ISyncJobRepository
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)


def _translate_mutation_log(
    log: MutationLog,
) -> list["GraphMutationOperation"]:
    """Convert shared-kernel MutationLog to graph-domain MutationOperation list.

    Maps:
      NodeMutation(UPSERT) → GraphMutationOperation(CREATE, NODE)
      NodeMutation(DELETE) → GraphMutationOperation(DELETE, NODE)
      EdgeMutation(UPSERT) → GraphMutationOperation(CREATE, EDGE)
      EdgeMutation(DELETE) → GraphMutationOperation(DELETE, EDGE)

    Lazy-imports from graph.domain to avoid pulling in the full graph stack
    (which requires psycopg2/age) at module load time.
    """
    from graph.domain.value_objects import (
        EntityType,
        MutationOperation as GraphMutOp,
        MutationOperationType,
    )

    ops: list[GraphMutOp] = []
    for record in log.records:
        if record.is_node:
            node = record.as_node
            if node.operation == MutationOperation.UPSERT:
                ops.append(
                    GraphMutOp(
                        op=MutationOperationType.CREATE,
                        type=EntityType.NODE,
                        id=node.node_id,
                        label=node.label,
                        set_properties=node.properties if node.properties else None,
                    )
                )
            else:
                ops.append(
                    GraphMutOp(
                        op=MutationOperationType.DELETE,
                        type=EntityType.NODE,
                        id=node.node_id,
                    )
                )
        else:
            edge = record.as_edge
            if edge.operation == MutationOperation.UPSERT:
                ops.append(
                    GraphMutOp(
                        op=MutationOperationType.CREATE,
                        type=EntityType.EDGE,
                        label=edge.relation,
                        start_id=edge.source_id,
                        end_id=edge.target_id,
                        set_properties=edge.properties if edge.properties else None,
                    )
                )
            else:
                ops.append(
                    GraphMutOp(
                        op=MutationOperationType.DELETE,
                        type=EntityType.EDGE,
                        start_id=edge.source_id,
                        end_id=edge.target_id,
                    )
                )
    return ops


class SyncJobWorker:
    """Background polling worker that executes pending sync jobs.

    Picks up PENDING jobs from the repository and runs them through
    the full ingestion + extraction + graph-write pipeline.
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker[AsyncSession]",
        sync_job_repo: "ISyncJobRepository",
        job_package_store: "InMemoryJobPackageStore",
        connection_pool: "ConnectionPool",
        db_settings: "DatabaseSettings",
        fernet_key: str,
        poll_interval_seconds: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._sync_job_repo = sync_job_repo
        self._job_package_store = job_package_store
        self._connection_pool = connection_pool
        self._db_settings = db_settings
        self._fernet_key = fernet_key
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background polling loop."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("sync_job_worker_started", poll_interval=self._poll_interval)

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("sync_job_worker_stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._process_pending()
            except Exception as exc:
                logger.error("sync_job_worker_poll_error", error=str(exc))
            await asyncio.sleep(self._poll_interval)

    async def _process_pending(self) -> None:
        """Fetch and execute all currently pending jobs."""
        pending = await self._sync_job_repo.list_pending()
        for job in pending:
            try:
                await self._execute_job(job)
            except Exception as exc:
                logger.error(
                    "sync_job_execution_error",
                    sync_job_id=job.id.value,
                    error=str(exc),
                )

    async def _execute_job(self, job: SyncJob) -> None:
        """Execute a single pending sync job end-to-end."""
        log = logger.bind(sync_job_id=job.id.value, data_source_id=job.data_source_id)

        # Transition to RUNNING
        job.start()
        await self._sync_job_repo.save(job)
        log.info("sync_job_running")

        try:
            package = await self._run_ingestion(job)
            pkg_id = await self._job_package_store.store(package)
            job.complete(job_package_id=pkg_id)
            await self._sync_job_repo.save(job)
            log.info("sync_job_completed", pkg_id=pkg_id)
        except Exception as exc:
            error_msg = str(exc)
            log.error("sync_job_ingestion_failed", error=error_msg)
            job.fail(error_message=error_msg)
            await self._sync_job_repo.save(job)
            return

        # Load package and run extraction → graph write
        loaded_pkg = await self._job_package_store.load(pkg_id)
        if loaded_pkg is None:
            log.warning("sync_job_package_missing", pkg_id=pkg_id)
            return

        try:
            from extraction.infrastructure.agents.python_ast_agent import (
                PythonAstSyntheticExtractionAgent,
            )

            agent = PythonAstSyntheticExtractionAgent()
            mutation_log = await agent.extract(loaded_pkg)
            log.info(
                "sync_job_extraction_complete",
                nodes=mutation_log.node_count,
                edges=mutation_log.edge_count,
            )
            self._apply_to_graph(mutation_log)
            log.info("sync_job_graph_write_complete")
        except Exception as exc:
            log.error("sync_job_extraction_or_graph_error", error=str(exc))

    async def _run_ingestion(self, job: SyncJob):  # type: ignore[return]
        """Fetch data source config and run the adapter."""
        from infrastructure.outbox.repository import OutboxRepository
        from ingestion.infrastructure.adapters.github import GitHubAdapter, GitHubConfig
        from management.domain.value_objects import DataSourceId
        from management.infrastructure.data_source_repository import (
            DataSourceRepository,
        )
        from management.infrastructure.fernet_credential_store import (
            FernetCredentialStore,
        )
        from shared_kernel.job_package import JobPackage

        async with self._session_factory() as session:
            outbox = OutboxRepository(session=session)
            ds_repo = DataSourceRepository(session=session, outbox=outbox)
            ds = await ds_repo.get_by_id(DataSourceId(value=job.data_source_id))

        if ds is None:
            raise ValueError(f"DataSource {job.data_source_id} not found")

        # Decrypt credentials (may not be stored if token was provided inline)
        credentials: dict[str, str] = {}
        if ds.credentials_path:
            try:
                async with self._session_factory() as session:
                    cred_store = FernetCredentialStore(
                        session=session, fernet_key=self._fernet_key
                    )
                    credentials = await cred_store.retrieve(
                        ds.credentials_path, ds.tenant_id
                    )
            except KeyError:
                pass

        config = ds.connection_config
        token = credentials.get("token", credentials.get("github_token", ""))
        adapter = GitHubAdapter(
            GitHubConfig(
                owner=config.get("owner", ""),
                repo=config.get("repo", ""),
                token=token,
                branch=config.get("branch") or None,
            )
        )

        changeset = await adapter.fetch_changeset(since_cursor=None)
        manifest, raw_files = changeset.to_manifest_and_raw_files()

        return JobPackage.create(
            knowledge_graph_id=job.knowledge_graph_id,
            data_source_id=job.data_source_id,
            tenant_id=job.tenant_id,
            adapter_type=job.adapter_type,
            manifest=manifest,
            raw_files=raw_files,
        )

    def _apply_to_graph(self, mutation_log: MutationLog) -> None:
        """Translate MutationLog and apply to the AGE graph (synchronous)."""
        from graph.infrastructure.age_bulk_loading import AgeBulkLoadingStrategy
        from graph.infrastructure.age_client import AgeGraphClient
        from graph.infrastructure.graph_provisioning_handler import graph_name_for_kg
        from graph.infrastructure.mutation_applier import MutationApplier
        from graph.infrastructure.type_definition_repository import (
            InMemoryTypeDefinitionRepository,
        )
        from graph.application.services.graph_mutation_service import (
            GraphMutationService,
        )
        from infrastructure.database.connection import ConnectionFactory

        graph_name = graph_name_for_kg(mutation_log.knowledge_graph_id)
        factory = ConnectionFactory(self._db_settings, pool=self._connection_pool)
        client = AgeGraphClient(
            self._db_settings, connection_factory=factory, graph_name=graph_name
        )
        client.connect()
        try:
            strategy = AgeBulkLoadingStrategy()
            applier = MutationApplier(client=client, bulk_loading_strategy=strategy)
            # Use a fresh InMemoryTypeDefinitionRepository per call
            # (matches the graph/dependencies.py pattern)
            type_def_repo = InMemoryTypeDefinitionRepository()
            service = GraphMutationService(
                mutation_applier=applier,
                type_definition_repository=type_def_repo,
            )
            ops = _translate_mutation_log(mutation_log)
            if ops:
                service.apply_mutations(ops)
        finally:
            client.disconnect()
