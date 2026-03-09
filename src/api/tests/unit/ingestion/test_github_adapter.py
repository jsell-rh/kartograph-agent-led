"""Unit tests for GitHubAdapter (AIHCM-177).

Tests verify adapter behavior using mocked httpx responses.
No real GitHub API calls are made in unit tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.infrastructure.adapters.github import GitHubAdapter, GitHubConfig
from ingestion.ports.adapters import IIngestionAdapter, IngestionChangeset
from shared_kernel.job_package import ChangeOperation


class TestGitHubConfig:
    """Tests for GitHubConfig value object."""

    def test_create_with_required_fields(self):
        """GitHubConfig should store owner, repo, and token."""
        config = GitHubConfig(
            owner="myorg",
            repo="myrepo",
            token="ghp_test123",
        )
        assert config.owner == "myorg"
        assert config.repo == "myrepo"
        assert config.token == "ghp_test123"
        assert config.base_url == "https://api.github.com"

    def test_default_base_url(self):
        """base_url defaults to GitHub API."""
        config = GitHubConfig(owner="o", repo="r", token="t")
        assert config.base_url == "https://api.github.com"

    def test_custom_base_url_for_github_enterprise(self):
        """base_url can be overridden for GitHub Enterprise."""
        config = GitHubConfig(
            owner="o",
            repo="r",
            token="t",
            base_url="https://github.mycompany.com/api/v3",
        )
        assert config.base_url == "https://github.mycompany.com/api/v3"


class TestGitHubAdapterImplementsPort:
    """Tests that GitHubAdapter satisfies IIngestionAdapter protocol."""

    def test_github_adapter_implements_protocol(self):
        """GitHubAdapter should satisfy the IIngestionAdapter protocol."""
        config = GitHubConfig(owner="o", repo="r", token="t")
        adapter = GitHubAdapter(config=config)
        assert isinstance(adapter, IIngestionAdapter)


class TestGitHubAdapterFetchChangeset:
    """Tests for GitHubAdapter.fetch_changeset() using mocked HTTP."""

    def _make_adapter(self, token: str = "ghp_test") -> GitHubAdapter:
        config = GitHubConfig(owner="myorg", repo="myrepo", token=token)
        return GitHubAdapter(config=config)

    @pytest.mark.asyncio
    async def test_fetch_changeset_no_cursor_fetches_default_branch(self):
        """Without a cursor, adapter fetches the default branch's latest state."""
        adapter = self._make_adapter()
        mock_response_commits = MagicMock()
        mock_response_commits.json.return_value = [
            {"sha": "abc123", "commit": {"message": "init"}}
        ]
        mock_response_commits.raise_for_status = MagicMock()

        mock_response_tree = MagicMock()
        mock_response_tree.json.return_value = {
            "sha": "abc123",
            "tree": [
                {"path": "README.md", "type": "blob", "sha": "sha1"},
                {"path": "src/app.py", "type": "blob", "sha": "sha2"},
            ],
            "truncated": False,
        }
        mock_response_tree.raise_for_status = MagicMock()

        mock_response_readme = MagicMock()
        mock_response_readme.content = b"# Hello"
        mock_response_readme.raise_for_status = MagicMock()

        mock_response_app = MagicMock()
        mock_response_app.content = b"print('hello')"
        mock_response_app.raise_for_status = MagicMock()

        with patch(
            "ingestion.infrastructure.adapters.github.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                side_effect=[
                    mock_response_commits,
                    mock_response_tree,
                    mock_response_readme,
                    mock_response_app,
                ]
            )

            changeset = await adapter.fetch_changeset(since_cursor=None)

        assert isinstance(changeset, IngestionChangeset)
        assert changeset.next_cursor == "abc123"
        assert len(changeset.entries) == 2

    @pytest.mark.asyncio
    async def test_fetch_changeset_with_cursor_fetches_diff(self):
        """With a cursor, adapter fetches only changed files since that commit."""
        adapter = self._make_adapter()

        mock_compare = MagicMock()
        mock_compare.raise_for_status = MagicMock()
        mock_compare.json.return_value = {
            "base_commit": {"sha": "old_sha"},
            "head_commit": {"sha": "new_sha"},
            "files": [
                {"filename": "src/app.py", "status": "modified", "sha": "newsha1"},
                {"filename": "old.py", "status": "removed", "sha": "oldsha2"},
                {"filename": "new_file.py", "status": "added", "sha": "newsha3"},
            ],
        }

        mock_file_content = MagicMock()
        mock_file_content.raise_for_status = MagicMock()
        mock_file_content.content = b"updated content"

        mock_new_file_content = MagicMock()
        mock_new_file_content.raise_for_status = MagicMock()
        mock_new_file_content.content = b"new content"

        with patch(
            "ingestion.infrastructure.adapters.github.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                side_effect=[
                    mock_compare,
                    mock_file_content,  # for src/app.py
                    mock_new_file_content,  # for new_file.py
                ]
            )

            changeset = await adapter.fetch_changeset(since_cursor="old_sha")

        assert changeset.next_cursor == "new_sha"
        paths = {e.path: e.operation for e in changeset.entries}
        assert paths["src/app.py"] == ChangeOperation.UPDATE
        assert paths["old.py"] == ChangeOperation.DELETE
        assert paths["new_file.py"] == ChangeOperation.ADD

    @pytest.mark.asyncio
    async def test_fetch_changeset_delete_entries_have_no_content(self):
        """DELETE entries should have content=None."""
        adapter = self._make_adapter()

        mock_compare = MagicMock()
        mock_compare.raise_for_status = MagicMock()
        mock_compare.json.return_value = {
            "base_commit": {"sha": "old"},
            "head_commit": {"sha": "new"},
            "files": [
                {"filename": "gone.py", "status": "removed", "sha": "oldsha"},
            ],
        }

        with patch(
            "ingestion.infrastructure.adapters.github.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_compare)

            changeset = await adapter.fetch_changeset(since_cursor="old")

        deleted = [e for e in changeset.entries if e.path == "gone.py"]
        assert len(deleted) == 1
        assert deleted[0].operation == ChangeOperation.DELETE
        assert deleted[0].content is None

    @pytest.mark.asyncio
    async def test_fetch_changeset_returns_empty_when_no_changes(self):
        """When there are no file changes, entries list should be empty."""
        adapter = self._make_adapter()

        mock_compare = MagicMock()
        mock_compare.raise_for_status = MagicMock()
        mock_compare.json.return_value = {
            "base_commit": {"sha": "old"},
            "head_commit": {"sha": "old"},  # same sha = no changes
            "files": [],
        }

        with patch(
            "ingestion.infrastructure.adapters.github.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_compare)

            changeset = await adapter.fetch_changeset(since_cursor="old")

        assert changeset.entries == []
        assert changeset.next_cursor == "old"


class TestIngestionChangeset:
    """Tests for IngestionChangeset value object."""

    def test_to_manifest_and_raw_files(self):
        """to_manifest_and_raw_files() should split into SyncManifest + raw bytes."""
        from ingestion.ports.adapters import ChangesetEntry

        entries = [
            ChangesetEntry(
                path="a.py",
                operation=ChangeOperation.ADD,
                content=b"hello",
                content_hash="h1",
            ),
            ChangesetEntry(
                path="b.py",
                operation=ChangeOperation.DELETE,
                content=None,
                content_hash=None,
            ),
        ]
        changeset = IngestionChangeset(entries=entries, next_cursor="sha123")
        manifest, raw_files = changeset.to_manifest_and_raw_files()

        assert len(manifest.entries) == 2
        assert raw_files == {"a.py": b"hello"}
        assert "b.py" not in raw_files
