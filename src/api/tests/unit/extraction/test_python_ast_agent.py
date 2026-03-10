"""Unit tests for PythonAstSyntheticExtractionAgent (AIHCM-174).

Validates that the AST-level synthetic agent produces richer graph
output: Module, Function, Class nodes + DEFINES/IMPORTS edges.
"""

from __future__ import annotations

import pytest

from extraction.infrastructure.agents.python_ast_agent import (
    PythonAstSyntheticExtractionAgent,
)
from extraction.ports.agents import IExtractionAgent
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import (
    ChangeOperation,
    JobPackage,
    ManifestEntry,
    SyncManifest,
)
from shared_kernel.mutation_log import MutationOperation


def _make_pkg(raw_files: dict[str, bytes]) -> JobPackage:
    entries = [
        ManifestEntry(path=p, operation=ChangeOperation.ADD, content_hash="abc")
        for p in raw_files
    ]
    return JobPackage.create(
        knowledge_graph_id="kg-1",
        data_source_id="ds-1",
        tenant_id="t-1",
        adapter_type=DataSourceAdapterType.GITHUB,
        manifest=SyncManifest(entries=entries),
        raw_files=raw_files,
    )


SIMPLE_MODULE = b"""\
import os
import sys

class MyClass:
    def method_one(self):
        pass

def top_level_func(x, y):
    return x + y
"""

MODULE_WITH_CALLS = b"""\
import os

def helper():
    return os.getcwd()

def main():
    result = helper()
    return result
"""


class TestPythonAstAgentProtocol:
    def test_implements_iextraction_agent(self):
        agent = PythonAstSyntheticExtractionAgent()
        assert isinstance(agent, IExtractionAgent)


class TestPythonAstAgentModuleNode:
    @pytest.mark.asyncio
    async def test_produces_module_node_for_python_file(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        labels = {r.as_node.label for r in result.records if r.is_node}
        assert "Module" in labels

    @pytest.mark.asyncio
    async def test_module_node_has_path_property(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        modules = [
            r.as_node
            for r in result.records
            if r.is_node and r.as_node.label == "Module"
        ]
        assert len(modules) == 1
        assert modules[0].properties["path"] == "src/app.py"


class TestPythonAstAgentFunctionNodes:
    @pytest.mark.asyncio
    async def test_produces_function_nodes(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        func_names = {
            r.as_node.properties["name"]
            for r in result.records
            if r.is_node and r.as_node.label == "Function"
        }
        assert "top_level_func" in func_names
        assert "method_one" in func_names

    @pytest.mark.asyncio
    async def test_function_node_has_line_number(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        funcs = [
            r.as_node
            for r in result.records
            if r.is_node and r.as_node.label == "Function"
        ]
        for func in funcs:
            assert "line" in func.properties
            assert isinstance(func.properties["line"], int)


class TestPythonAstAgentClassNodes:
    @pytest.mark.asyncio
    async def test_produces_class_nodes(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        class_names = {
            r.as_node.properties["name"]
            for r in result.records
            if r.is_node and r.as_node.label == "Class"
        }
        assert "MyClass" in class_names


class TestPythonAstAgentEdges:
    @pytest.mark.asyncio
    async def test_produces_defines_edges_from_module_to_functions(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        edge_relations = {r.as_edge.relation for r in result.records if r.is_edge}
        assert "DEFINES" in edge_relations

    @pytest.mark.asyncio
    async def test_module_defines_class(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        define_edges = [
            r.as_edge
            for r in result.records
            if r.is_edge and r.as_edge.relation == "DEFINES"
        ]
        assert len(define_edges) >= 1


class TestPythonAstAgentNonPythonFiles:
    @pytest.mark.asyncio
    async def test_non_python_file_produces_file_node(self):
        pkg = _make_pkg({"README.md": b"# Hello World"})
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        labels = {r.as_node.label for r in result.records if r.is_node}
        assert "File" in labels

    @pytest.mark.asyncio
    async def test_mixed_files_produce_mixed_nodes(self):
        pkg = _make_pkg(
            {
                "src/app.py": SIMPLE_MODULE,
                "README.md": b"# Hello",
            }
        )
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        labels = {r.as_node.label for r in result.records if r.is_node}
        assert "Module" in labels
        assert "File" in labels


class TestPythonAstAgentDeleteEntries:
    @pytest.mark.asyncio
    async def test_delete_entry_produces_delete_mutation(self):
        pkg = JobPackage.create(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=SyncManifest(
                entries=[
                    ManifestEntry(
                        path="old/app.py",
                        operation=ChangeOperation.DELETE,
                        content_hash=None,
                    )
                ]
            ),
            raw_files={},
        )
        agent = PythonAstSyntheticExtractionAgent()
        result = await agent.extract(pkg)

        deletes = [
            r
            for r in result.records
            if r.is_node and r.as_node.operation == MutationOperation.DELETE
        ]
        assert len(deletes) >= 1


class TestPythonAstAgentDeterminism:
    @pytest.mark.asyncio
    async def test_same_input_produces_same_node_ids(self):
        pkg = _make_pkg({"src/app.py": SIMPLE_MODULE})
        agent = PythonAstSyntheticExtractionAgent()

        result1 = await agent.extract(pkg)
        result2 = await agent.extract(pkg)

        ids1 = {r.as_node.node_id for r in result1.records if r.is_node}
        ids2 = {r.as_node.node_id for r in result2.records if r.is_node}
        assert ids1 == ids2
