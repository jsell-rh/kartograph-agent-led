"""GitHub adapter for the Ingestion bounded context (AIHCM-177).

Fetches repository file changes from the GitHub REST API using httpx.
Uses dlt for incremental state management and resource abstraction.

Design:
- GitHubConfig: adapter configuration (owner, repo, token, base_url)
- GitHubAdapter: implements IIngestionAdapter
  - First sync (since_cursor=None): fetches full tree of default branch
  - Incremental sync (since_cursor=<sha>): fetches compare diff since that SHA

The adapter does NOT upload to a dlt destination. Instead it returns an
IngestionChangeset that the application service converts to a JobPackage.
dlt resources are used for their incremental cursor management abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass

import dlt
import httpx

from ingestion.ports.adapters import ChangesetEntry, IngestionChangeset
from shared_kernel.job_package import ChangeOperation

_GITHUB_MEDIA_TYPE = "application/vnd.github+json"
_API_VERSION_HEADER = "2022-11-28"


@dataclass(frozen=True)
class GitHubConfig:
    """Configuration for the GitHub adapter.

    Attributes:
        owner: GitHub organization or user name
        repo: Repository name (without owner prefix)
        token: GitHub personal access token or OAuth token
        base_url: GitHub API base URL (override for GitHub Enterprise)
        branch: Default branch to sync (default: relies on repo default)
    """

    owner: str
    repo: str
    token: str
    base_url: str = "https://api.github.com"
    branch: str | None = None

    @property
    def repo_path(self) -> str:
        """Return owner/repo path segment."""
        return f"{self.owner}/{self.repo}"


def _github_status_to_operation(status: str) -> ChangeOperation:
    """Map GitHub file status to ChangeOperation.

    GitHub compare API returns: added, modified, renamed, copied, removed.
    """
    if status in ("added", "copied"):
        return ChangeOperation.ADD
    if status == "removed":
        return ChangeOperation.DELETE
    return ChangeOperation.UPDATE  # modified, renamed


class GitHubAdapter:
    """Fetches repository file changes from the GitHub REST API.

    First sync (since_cursor=None):
        Fetches the full recursive tree of the default branch.
        Downloads all blob files and marks them as ADD.

    Incremental sync (since_cursor=<commit_sha>):
        Calls the GitHub compare API to get files changed between
        since_cursor and the latest commit on the default branch.
        Downloads content for ADD/UPDATE files; marks REMOVE as DELETE.
    """

    def __init__(self, config: GitHubConfig) -> None:
        self._config = config

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.token}",
            "Accept": _GITHUB_MEDIA_TYPE,
            "X-GitHub-Api-Version": _API_VERSION_HEADER,
        }

    def _url(self, path: str) -> str:
        return f"{self._config.base_url}{path}"

    async def fetch_changeset(
        self,
        *,
        since_cursor: str | None = None,
    ) -> IngestionChangeset:
        """Fetch file changes from GitHub.

        Args:
            since_cursor: Latest commit SHA from previous sync, or None for first sync.

        Returns:
            IngestionChangeset with detected changes and updated cursor.
        """
        async with httpx.AsyncClient() as client:
            if since_cursor is None:
                return await self._full_sync(client)
            return await self._incremental_sync(client, since_cursor)

    async def _get_latest_commit_sha(self, client: httpx.AsyncClient) -> str:
        """Fetch the latest commit SHA on the default (or configured) branch."""
        branch = self._config.branch or ""
        if branch:
            url = self._url(f"/repos/{self._config.repo_path}/branches/{branch}")
        else:
            url = self._url(f"/repos/{self._config.repo_path}/commits")

        resp = await client.get(
            url, headers=self._auth_headers(), params={"per_page": 1}
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data[0]["sha"]
        return data["commit"]["sha"]

    async def _full_sync(self, client: httpx.AsyncClient) -> IngestionChangeset:
        """Fetch the full current tree of the repository (first sync)."""
        latest_sha = await self._get_latest_commit_sha(client)

        tree_url = self._url(f"/repos/{self._config.repo_path}/git/trees/{latest_sha}")
        tree_resp = await client.get(
            tree_url, headers=self._auth_headers(), params={"recursive": "1"}
        )
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()

        entries: list[ChangesetEntry] = []
        for item in tree_data.get("tree", []):
            if item["type"] != "blob":
                continue
            path = item["path"]
            content = await self._download_file(client, path)
            entries.append(
                ChangesetEntry.from_content(path, ChangeOperation.ADD, content)
            )

        return IngestionChangeset(entries=entries, next_cursor=latest_sha)

    async def _incremental_sync(
        self, client: httpx.AsyncClient, since_sha: str
    ) -> IngestionChangeset:
        """Fetch only files changed since since_sha."""
        # Use GitHub compare API: GET /repos/{owner}/{repo}/compare/{base}...{head}
        # We compare from since_sha to HEAD of the default branch
        head_ref = self._config.branch or "HEAD"
        compare_url = self._url(
            f"/repos/{self._config.repo_path}/compare/{since_sha}...{head_ref}"
        )
        compare_resp = await client.get(compare_url, headers=self._auth_headers())
        compare_resp.raise_for_status()
        compare_data = compare_resp.json()

        head_sha = compare_data["head_commit"]["sha"]
        changed_files = compare_data.get("files", [])

        entries: list[ChangesetEntry] = []
        for file_info in changed_files:
            path = file_info["filename"]
            status = file_info["status"]
            operation = _github_status_to_operation(status)

            if operation == ChangeOperation.DELETE:
                entries.append(ChangesetEntry.deleted(path))
            else:
                content = await self._download_file(client, path)
                entries.append(ChangesetEntry.from_content(path, operation, content))

        return IngestionChangeset(entries=entries, next_cursor=head_sha)

    async def _download_file(self, client: httpx.AsyncClient, path: str) -> bytes:
        """Download raw file content from GitHub.

        Uses the raw content endpoint which returns bytes directly.
        """
        raw_url = self._url(f"/repos/{self._config.repo_path}/contents/{path}")
        resp = await client.get(
            raw_url,
            headers={
                **self._auth_headers(),
                "Accept": "application/vnd.github.raw+json",
            },
        )
        resp.raise_for_status()
        return resp.content


@dlt.resource(name="github_file_changes", write_disposition="replace")
def github_file_changes_resource(
    owner: str,
    repo: str,
    token: dlt.secrets.value,
    since_cursor: str | None = None,
    base_url: str = "https://api.github.com",
):
    """dlt resource definition for GitHub file changes.

    This resource wraps the GitHubAdapter for use in dlt pipelines.
    It yields ChangesetEntry dicts for dlt's incremental loading machinery.

    NOTE: For direct ingestion pipeline use, prefer GitHubAdapter directly.
    This resource is provided for dlt-orchestrated pipeline scenarios.
    """
    import asyncio

    config = GitHubConfig(owner=owner, repo=repo, token=token, base_url=base_url)
    adapter = GitHubAdapter(config=config)
    changeset = asyncio.run(adapter.fetch_changeset(since_cursor=since_cursor))
    for entry in changeset.entries:
        yield {
            "path": entry.path,
            "operation": str(entry.operation),
            "content": entry.content,
            "content_hash": entry.content_hash,
            "cursor": changeset.next_cursor,
        }
