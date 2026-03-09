"""Architecture boundary tests for Ingestion bounded context (AIHCM-176).

Enforces DDD layering rules: domain knows nothing about infrastructure,
application knows nothing about infrastructure, ports define interfaces only.
"""

from pytest_archon import archrule


class TestIngestionDomainLayerBoundaries:
    """Tests that the Ingestion domain layer has no forbidden dependencies."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer should not depend on infrastructure."""
        (
            archrule("ingestion_domain_no_infrastructure")
            .match("ingestion.domain*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_domain_does_not_import_application(self):
        """Domain layer should not depend on application layer."""
        (
            archrule("ingestion_domain_no_application")
            .match("ingestion.domain*")
            .should_not_import("ingestion.application*")
            .check("ingestion")
        )

    def test_domain_does_not_import_fastapi(self):
        """Domain layer should not depend on FastAPI."""
        (
            archrule("ingestion_domain_no_fastapi")
            .match("ingestion.domain*")
            .should_not_import("fastapi*", "starlette*")
            .check("ingestion")
        )

    def test_domain_does_not_import_sqlalchemy(self):
        """Domain layer should not depend on SQLAlchemy."""
        (
            archrule("ingestion_domain_no_sqlalchemy")
            .match("ingestion.domain*")
            .should_not_import("sqlalchemy*")
            .check("ingestion")
        )


class TestIngestionPortsLayerBoundaries:
    """Tests that the Ingestion ports layer has no forbidden dependencies."""

    def test_ports_does_not_import_infrastructure(self):
        """Ports should not depend on infrastructure implementations."""
        (
            archrule("ingestion_ports_no_infrastructure")
            .match("ingestion.ports*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_ports_does_not_import_application(self):
        """Ports should not depend on application layer."""
        (
            archrule("ingestion_ports_no_application")
            .match("ingestion.ports*")
            .should_not_import("ingestion.application*")
            .check("ingestion")
        )


class TestIngestionApplicationLayerBoundaries:
    """Tests that the Ingestion application layer has appropriate dependencies."""

    def test_application_does_not_import_infrastructure(self):
        """Application layer should not directly import infrastructure."""
        (
            archrule("ingestion_application_no_infrastructure")
            .match("ingestion.application*")
            .should_not_import("ingestion.infrastructure*")
            .check("ingestion")
        )

    def test_application_can_import_domain_and_ports(self):
        """Application layer should be able to import domain and ports."""
        (
            archrule("ingestion_application_may_import_domain_ports")
            .match("ingestion.application*")
            .may_import("ingestion.domain*", "ingestion.ports*")
            .check("ingestion")
        )


class TestIngestionInfrastructureLayerBoundaries:
    """Tests that Ingestion infrastructure has appropriate dependencies."""

    def test_infrastructure_does_not_import_application(self):
        """Infrastructure should not depend on application layer."""
        (
            archrule("ingestion_infrastructure_no_application")
            .match("ingestion.infrastructure*")
            .should_not_import("ingestion.application*")
            .check("ingestion")
        )

    def test_infrastructure_can_import_domain_and_ports(self):
        """Infrastructure can import domain and ports."""
        (
            archrule("ingestion_infrastructure_may_import_domain_ports")
            .match("ingestion.infrastructure*")
            .may_import("ingestion.domain*", "ingestion.ports*")
            .check("ingestion")
        )


class TestIngestionCrossContextBoundaries:
    """Tests that Ingestion context boundaries are respected."""

    def test_ingestion_does_not_import_graph_domain(self):
        """Ingestion should not import Graph domain objects."""
        (
            archrule("ingestion_no_graph_domain")
            .match("ingestion.domain*", "ingestion.application*", "ingestion.ports*")
            .should_not_import("graph.domain*")
            .check("ingestion")
        )

    def test_ingestion_does_not_import_query_internals(self):
        """Ingestion should not import Query context internals."""
        (
            archrule("ingestion_no_query_internals")
            .match("ingestion*")
            .should_not_import(
                "query.domain*", "query.application*", "query.infrastructure*"
            )
            .check("ingestion")
        )

    def test_ingestion_can_import_shared_kernel(self):
        """Ingestion may import from shared_kernel."""
        (
            archrule("ingestion_may_import_shared_kernel")
            .match("ingestion*")
            .may_import("shared_kernel*")
            .check("ingestion")
        )
