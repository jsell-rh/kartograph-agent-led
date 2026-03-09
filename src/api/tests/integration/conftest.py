"""Integration test fixtures for database and authentication tests.

These fixtures require running services:
- PostgreSQL instance with AGE extension
- Keycloak for authentication tests

Use docker-compose for testing.

IMPORTANT: Environment variables must be set at the top of this file,
before ANY imports that might trigger settings caching.
"""

# Step 1: Set environment variables FIRST, before any other imports
import os

# Step 2: Now safe to import other modules
from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.database.engines import create_write_engine
from infrastructure.settings import DatabaseSettings

os.environ.setdefault("SPICEDB_ENDPOINT", "localhost:50051")
os.environ.setdefault("SPICEDB_PRESHARED_KEY", "changeme")
os.environ.setdefault("SPICEDB_USE_TLS", "true")

# Configure SpiceDB client to use the self-signed certificate
_cert_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "certs", "spicedb-cert.pem"
)
if os.path.exists(_cert_path):
    os.environ.setdefault("SPICEDB_CERT_PATH", os.path.abspath(_cert_path))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires database)",
    )
    config.addinivalue_line(
        "markers",
        "keycloak: mark test as requiring Keycloak authentication server",
    )


@pytest.fixture(scope="session")
def integration_db_settings() -> DatabaseSettings:
    """Database settings for integration tests.

    Override with environment variables:
        KARTOGRAPH_DB_HOST, KARTOGRAPH_DB_PORT, etc.
    """
    return DatabaseSettings(
        host=os.getenv("KARTOGRAPH_DB_HOST", "localhost"),
        port=int(os.getenv("KARTOGRAPH_DB_PORT", "5432")),
        database=os.getenv("KARTOGRAPH_DB_DATABASE", "kartograph"),
        username=os.getenv("KARTOGRAPH_DB_USERNAME", "kartograph"),
        password=SecretStr(
            os.getenv("KARTOGRAPH_DB_PASSWORD", "kartograph_dev_password")
        ),
        graph_name=os.getenv("KARTOGRAPH_DB_GRAPH_NAME", "test_graph"),
    )


@pytest.fixture(scope="session")
def integration_connection_pool(
    integration_db_settings: DatabaseSettings,
) -> Generator[ConnectionPool, None, None]:
    """Session-scoped connection pool for integration tests."""
    pool = ConnectionPool(integration_db_settings)
    yield pool
    pool.close_all()


@pytest.fixture
def graph_client(
    integration_db_settings: DatabaseSettings,
    integration_connection_pool: ConnectionPool,
) -> Generator[AgeGraphClient, None, None]:
    """Provide a connected graph client for integration tests.

    Automatically connects and disconnects around each test.
    Uses connection pool to match production behavior.
    """
    factory = ConnectionFactory(
        integration_db_settings, pool=integration_connection_pool
    )
    client = AgeGraphClient(integration_db_settings, connection_factory=factory)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture
def clean_graph(graph_client: AgeGraphClient):
    """Ensure a clean graph state before and after each test.

    Deletes all nodes and relationships in the test graph.
    """
    # Clean before test
    try:
        graph_client.execute_cypher("MATCH (n) DETACH DELETE n")
    except Exception:
        pass  # Graph might be empty or not exist

    yield graph_client

    # Clean after test
    try:
        graph_client.execute_cypher("MATCH (n) DETACH DELETE n")
    except Exception:
        pass


# =============================================================================
# Keycloak / OIDC Authentication Fixtures
# =============================================================================

# Set OIDC defaults for tests (can be overridden by env vars)
os.environ.setdefault(
    "KARTOGRAPH_OIDC_ISSUER_URL", "http://localhost:8080/realms/kartograph"
)
os.environ.setdefault("KARTOGRAPH_OIDC_CLIENT_ID", "kartograph-api")
os.environ.setdefault("KARTOGRAPH_OIDC_CLIENT_SECRET", "kartograph-api-secret")
os.environ.setdefault("SPICEDB_PRESHARED_KEY", "changeme")


@pytest.fixture(scope="session")
def oidc_settings():
    """OIDC settings for integration tests.

    Uses OIDCSettings from infrastructure, which reads from environment.
    Default issuer is localhost:8080 for host-based testing.

    For containerized tests, set KARTOGRAPH_OIDC_ISSUER_URL to use
    Docker service names (e.g., http://keycloak:8080/realms/kartograph).
    """
    from infrastructure.settings import get_oidc_settings

    # Clear the lru_cache to pick up test env vars
    get_oidc_settings.cache_clear()
    return get_oidc_settings()


@pytest.fixture
def keycloak_token_url(oidc_settings) -> str:
    """Keycloak token endpoint URL derived from OIDC settings."""
    return f"{oidc_settings.issuer_url}/protocol/openid-connect/token"


@pytest.fixture
def oidc_client_credentials(oidc_settings) -> dict[str, str]:
    """OIDC client credentials from settings."""
    return {
        "client_id": oidc_settings.client_id,
        "client_secret": oidc_settings.client_secret.get_secret_value(),
    }


@pytest.fixture
def get_test_token(keycloak_token_url: str, oidc_client_credentials: dict[str, str]):
    """Factory fixture to get access tokens for test users.

    Uses OAuth2 password grant (deprecated but acceptable for integration tests).
    Requires Keycloak to be running.

    Usage:
        def test_something(get_test_token):
            token = get_test_token("alice", "password")
            headers = {"Authorization": f"Bearer {token}"}
    """

    def _get_token(username: str, password: str) -> str:
        with httpx.Client() as client:
            response = client.post(
                keycloak_token_url,
                data={
                    "grant_type": "password",
                    "client_id": oidc_client_credentials["client_id"],
                    "client_secret": oidc_client_credentials["client_secret"],
                    "username": username,
                    "password": password,
                    "scope": "openid profile email",
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    return _get_token


@pytest.fixture
def alice_token(get_test_token) -> str:
    """Get access token for alice user."""
    return get_test_token("alice", "password")


@pytest.fixture
def bob_token(get_test_token) -> str:
    """Get access token for bob user."""
    return get_test_token("bob", "password")


@pytest.fixture
def auth_headers(alice_token: str) -> dict[str, str]:
    """Default auth headers using alice's token."""
    return {"Authorization": f"Bearer {alice_token}"}


@pytest.fixture
def bob_auth_headers(bob_token: str) -> dict[str, str]:
    """Default auth headers using bob's token."""
    return {"Authorization": f"Bearer {bob_token}"}


@pytest_asyncio.fixture
async def default_tenant_id(
    integration_db_settings: DatabaseSettings,
) -> AsyncGenerator[str, None]:
    """Get the default tenant ID from the database.

    The default tenant is created at app startup by TenantBootstrapService.
    This fixture queries the database directly to retrieve its ID for use
    in X-Tenant-ID headers during integration tests.

    Returns:
        The default tenant's ID (ULID string)
    """
    from infrastructure.settings import get_iam_settings

    iam_settings = get_iam_settings()
    engine = create_write_engine(integration_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        result = await session.execute(
            text("SELECT id FROM tenants WHERE name = :name"),
            {"name": iam_settings.default_tenant_name},
        )
        row = result.scalar_one_or_none()
        assert row is not None, (
            f"Default tenant '{iam_settings.default_tenant_name}' not found. "
            "Ensure app lifespan ran (use async_client fixture)."
        )
        yield row

    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_auth_headers(
    auth_headers: dict[str, str],
    default_tenant_id: str,
    alice_token: str,
    integration_db_settings: DatabaseSettings,
) -> AsyncGenerator[dict[str, str], None]:
    """Auth headers with X-Tenant-ID for integration tests.

    Merges the JWT Bearer auth headers with the default tenant's
    X-Tenant-ID header, making tenant context explicit in test requests
    instead of relying on single-tenant mode auto-selection.

    Also ensures the user has SpiceDB relationships on:
    - The default tenant (member role)
    - The default tenant's root workspace (admin role)

    This allows workspace integration tests to work with the new
    authorization enforcement.

    Cleans up all SpiceDB relationships written by this fixture after the
    test, preventing relationship accumulation across tests.

    Args:
        auth_headers: JWT Bearer auth headers
        default_tenant_id: The default tenant's ID
        alice_token: Alice's JWT token (for extracting user_id)
        integration_db_settings: Database settings for querying root workspace

    Yields:
        Headers dict with both Authorization and X-Tenant-ID
    """
    from jose import jwt as jose_jwt

    from infrastructure.authorization_dependencies import get_spicedb_client
    from shared_kernel.authorization.types import (
        ResourceType,
        format_resource,
        format_subject,
    )

    # Extract user_id from JWT claims
    claims = jose_jwt.get_unverified_claims(alice_token)
    user_id = claims["sub"]

    # Ensure alice has 'member' relationship on the default tenant in SpiceDB
    spicedb = get_spicedb_client()
    tenant_resource = format_resource(ResourceType.TENANT, default_tenant_id)
    user_subject = format_subject(ResourceType.USER, user_id)

    await spicedb.write_relationship(
        resource=tenant_resource,
        relation="member",
        subject=user_subject,
    )

    # Query database for the root workspace ID
    engine = create_write_engine(integration_db_settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        result = await session.execute(
            text(
                "SELECT id FROM workspaces WHERE tenant_id = :tenant_id AND is_root = true"
            ),
            {"tenant_id": default_tenant_id},
        )
        root_workspace_id = result.scalar_one_or_none()

    await engine.dispose()

    # Grant alice admin permission on the root workspace
    workspace_resource = None
    if root_workspace_id:
        workspace_resource = format_resource(ResourceType.WORKSPACE, root_workspace_id)

        await spicedb.write_relationship(
            resource=workspace_resource,
            relation="admin",
            subject=user_subject,
        )

    yield {**auth_headers, "X-Tenant-ID": default_tenant_id}

    # Teardown: remove SpiceDB relationships written by this fixture to prevent
    # state pollution across tests.
    try:
        await spicedb.delete_relationship(
            resource=tenant_resource,
            relation="member",
            subject=user_subject,
        )
    except Exception:
        pass  # Best-effort; relationship may already be gone

    if workspace_resource:
        try:
            await spicedb.delete_relationship(
                resource=workspace_resource,
                relation="admin",
                subject=user_subject,
            )
        except Exception:
            pass  # Best-effort; relationship may already be gone


@pytest_asyncio.fixture
async def bob_tenant_auth_headers(
    bob_auth_headers: dict[str, str],
    default_tenant_id: str,
    bob_token: str,
    integration_db_settings: DatabaseSettings,
) -> AsyncGenerator[dict[str, str], None]:
    """Auth headers with X-Tenant-ID for bob in integration tests.

    Grants bob 'member' role on the default tenant (NOT admin) so that
    bob can authenticate with a tenant context but will be denied admin
    operations. This is used to test authorization denial scenarios.

    Cleans up all SpiceDB relationships written by this fixture after the
    test, preventing relationship accumulation across tests.

    Args:
        bob_auth_headers: JWT Bearer auth headers for bob
        default_tenant_id: The default tenant's ID
        bob_token: Bob's JWT token (for extracting user_id)
        integration_db_settings: Database settings for querying root workspace

    Yields:
        Headers dict with both Authorization and X-Tenant-ID for bob
    """
    from jose import jwt as jose_jwt

    from infrastructure.authorization_dependencies import get_spicedb_client
    from shared_kernel.authorization.types import (
        ResourceType,
        format_resource,
        format_subject,
    )

    # Extract user_id from JWT claims
    claims = jose_jwt.get_unverified_claims(bob_token)
    user_id = claims["sub"]

    # Ensure bob has 'member' relationship on the default tenant in SpiceDB
    spicedb = get_spicedb_client()
    tenant_resource = format_resource(ResourceType.TENANT, default_tenant_id)
    user_subject = format_subject(ResourceType.USER, user_id)

    await spicedb.write_relationship(
        resource=tenant_resource,
        relation="member",
        subject=user_subject,
    )

    yield {**bob_auth_headers, "X-Tenant-ID": default_tenant_id}

    # Teardown: remove SpiceDB relationships written by this fixture.
    try:
        await spicedb.delete_relationship(
            resource=tenant_resource,
            relation="member",
            subject=user_subject,
        )
    except Exception:
        pass  # Best-effort; relationship may already be gone


@pytest_asyncio.fixture
async def clean_iam_tables(
    integration_db_settings: DatabaseSettings,
) -> AsyncGenerator[None, None]:
    """Clean all IAM SQL tables before and after each test.

    Provides the same SQL isolation as the iam-subpackage ``clean_iam_data``
    fixture but is available to all tests in the integration/ directory,
    including those that live outside the iam/ subdirectory (e.g.
    test_api_key_auth.py, test_auth_enforcement.py).

    Deletion order respects FK constraints:
    outbox -> api_keys -> groups -> users -> workspaces (children) ->
    workspaces (roots, non-default) -> tenants (non-default)
    """
    from infrastructure.settings import get_iam_settings

    default_tenant_name = get_iam_settings().default_tenant_name

    async def _cleanup() -> None:
        engine = create_write_engine(integration_db_settings)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            try:
                await session.execute(text("DELETE FROM outbox"))
                await session.execute(text("DELETE FROM api_keys"))
                await session.execute(text("DELETE FROM groups"))
                await session.execute(text("DELETE FROM users"))
                await session.execute(
                    text("DELETE FROM workspaces WHERE parent_workspace_id IS NOT NULL")
                )
                await session.execute(
                    text(
                        "DELETE FROM workspaces WHERE tenant_id IN "
                        "(SELECT id FROM tenants WHERE name != :name)"
                    ),
                    {"name": default_tenant_name},
                )
                await session.execute(
                    text("DELETE FROM tenants WHERE name != :name"),
                    {"name": default_tenant_name},
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await engine.dispose()

    await _cleanup()
    yield
    await _cleanup()
