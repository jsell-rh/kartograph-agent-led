"""Architecture boundary tests for Extraction bounded context (AIHCM-139)."""

from pytest_archon import archrule


class TestExtractionPortsBoundaries:
    """Tests that Extraction ports have no forbidden dependencies."""

    def test_extraction_ports_does_not_import_infrastructure(self):
        """Extraction ports should not depend on infrastructure."""
        (
            archrule("extraction_ports_no_infrastructure")
            .match("extraction.ports*")
            .should_not_import("extraction.infrastructure*")
            .check("extraction")
        )

    def test_extraction_ports_does_not_import_application(self):
        """Extraction ports should not depend on application layer."""
        (
            archrule("extraction_ports_no_application")
            .match("extraction.ports*")
            .should_not_import("extraction.application*")
            .check("extraction")
        )


class TestExtractionInfrastructureBoundaries:
    """Tests that Extraction infrastructure has appropriate dependencies."""

    def test_extraction_infrastructure_does_not_import_application(self):
        """Extraction infrastructure should not depend on application layer."""
        (
            archrule("extraction_infrastructure_no_application")
            .match("extraction.infrastructure*")
            .should_not_import("extraction.application*")
            .check("extraction")
        )

    def test_extraction_infrastructure_can_import_ports(self):
        """Extraction infrastructure can import ports (implements them)."""
        (
            archrule("extraction_infrastructure_may_import_ports")
            .match("extraction.infrastructure*")
            .may_import("extraction.ports*")
            .check("extraction")
        )


class TestExtractionSharedKernelBoundary:
    """Tests that Extraction context properly uses shared_kernel."""

    def test_extraction_can_import_shared_kernel(self):
        """Extraction context may import from shared_kernel."""
        (
            archrule("extraction_may_import_shared_kernel")
            .match("extraction*")
            .may_import("shared_kernel*")
            .check("extraction")
        )

    def test_extraction_does_not_import_ingestion_internals(self):
        """Extraction should not import Ingestion internals."""
        (
            archrule("extraction_no_ingestion_internals")
            .match("extraction*")
            .should_not_import(
                "ingestion.domain*",
                "ingestion.application*",
                "ingestion.infrastructure*",
            )
            .check("extraction")
        )
