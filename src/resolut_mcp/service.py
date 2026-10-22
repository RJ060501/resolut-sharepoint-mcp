"""Policy-aware tool implementations; independent of the MCP transport."""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Protocol
from collections.abc import AsyncIterator

from .config import Settings
from .errors import ConnectorError
from .extraction import extract_document
from .extract_worker import supported
from .models import DocumentRef, Principal, job_identifier
from .registry import Job, Registry


class GraphReader(Protocol):
    async def site(self, job: Job) -> dict[str, Any]: ...
    async def drives(self, job: Job) -> list[dict[str, Any]]: ...
    def children(self, job: Job, drive_id: str, folder_id: str | None = None) -> AsyncIterator[dict[str, Any]]: ...
    async def item(self, job: Job, drive_id: str, item_id: str) -> dict[str, Any]: ...
    def validate_item(self, job: Job, drive_id: str, item: dict[str, Any]) -> None: ...
    async def content(self, job: Job, drive_id: str, item_id: str) -> bytes: ...


class Service:
    def __init__(self, settings: Settings, registry: Registry, principal: Principal, graph: GraphReader) -> None:
        self.settings = settings
        self.registry = registry
        self.principal = principal
        self.graph = graph

    def guard(self, job: Job) -> Job:
        self.principal.require_active()
        return self.registry.require(job.job_id, job.site_id)

    def _jobs(self, job_id: str | None = None) -> tuple[list[Job], bool]:
        self.principal.require_active()
        if job_id is not None:
            return [self.registry.require(job_identifier(job_id))], True
        jobs = self.registry.approved_jobs()
        return jobs[:self.settings.max_sites], len(jobs) <= self.settings.max_sites

    async def list_approved_jobs(self) -> dict[str, Any]:
        jobs, complete = self._jobs()
        found = []
        for job in jobs:
            try:
                await self.graph.site(job)
                self.guard(job)
                found.append({"job_id": job.job_id, "name": job.display_name, "site_url": job.site_url})
            except ConnectorError as exc:
                if exc.code != "unavailable":
                    raise
        # A mid-flight block cancels the response, rather than returning stale approvals.
        for row in found:
            job = self.registry.require(row["job_id"])
            await self.graph.site(job)
            self.guard(job)
        return {"jobs": found, "complete": complete,
                "note": "Only currently approved jobs visible to your Microsoft identity are listed."}

    async def search_approved_documents(self, query: str, job_id: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or any(ord(c) < 32 for c in query):
            raise ConnectorError("invalid_request")
        words = query.casefold().split()
        jobs, complete = self._jobs(job_id)
        results: list[dict[str, Any]] = []
        examined = 0
        started = time.monotonic()
        limit_reasons = [] if complete else ["site_limit"]
        stop = False
        for job in jobs:
            try:
                self.guard(job)
                drives = await self.graph.drives(job)
            except ConnectorError as exc:
                if exc.code == "unavailable":
                    continue
                raise
            queue = deque((drive["id"], None, str(drive.get("name", "Documents")), 0) for drive in drives)
            visited = set()
            while queue and not stop:
                if time.monotonic() - started > self.settings.request_seconds - 10:
                    complete, stop = False, True
                    limit_reasons.append("time_limit")
                    break
                drive_id, folder_id, folder_path, depth = queue.popleft()
                key = (drive_id, folder_id)
                if key in visited:
                    continue
                visited.add(key)
                if depth > 64:
                    complete = False
                    limit_reasons.append("depth_limit")
                    continue
                try:
                    async for candidate in self.graph.children(job, drive_id, folder_id):
                        self.guard(job)
                        examined += 1
                        if examined > self.settings.max_scan_items:
                            complete, stop = False, True
                            limit_reasons.append("item_limit")
                            break
                        try:
                            self.graph.validate_item(job, drive_id, candidate)
                        except ConnectorError as exc:
                            if exc.code == "unavailable":
                                complete = False
                                limit_reasons.append("unverifiable_metadata")
                                continue
                            raise
                        name = candidate.get("name", "")
                        if not isinstance(name, str) or len(name) > 1000:
                            continue
                        if candidate.get("folder") is not None:
                            queue.append((drive_id, candidate["id"], f"{folder_path}/{name}", depth+1))
                            continue
                        if candidate.get("file") is None or not supported(name):
                            continue
                        if not all(word in f"{folder_path}/{name}".casefold() for word in words):
                            continue
                        ref = DocumentRef(job.job_id, job.site_id, drive_id, candidate["id"])
                        try:
                            current = await self.graph.item(job, drive_id, ref.item_id)
                        except ConnectorError as exc:
                            if exc.code == "unavailable":
                                continue
                            raise
                        self.guard(job)
                        if current.get("file") is None or not supported(current.get("name", "")):
                            continue
                        results.append({"document_id": ref.encode(), "job_id": job.job_id,
                                        "name": current["name"], "source_url": current["webUrl"],
                                        "etag": current.get("eTag"), "modified": current.get("lastModifiedDateTime")})
                        if len(results) >= self.settings.max_search_results:
                            complete, stop = False, True
                            limit_reasons.append("result_limit")
                            break
                except ConnectorError as exc:
                    if exc.code == "unavailable":
                        # An ACL denial can be skipped; a policy block must cancel
                        # the response rather than disguising a revoked site as empty.
                        self.guard(job)
                        # Do not reveal the path, name, or existence of denied folders.
                        continue
                    if exc.code == "deadline":
                        complete, stop = False, True
                        limit_reasons.append("pagination_limit")
                    else:
                        raise
            if stop:
                break
        # Reauthorize every surviving result after the scan. No shared metadata cache.
        verified = []
        for result in results:
            ref = DocumentRef.decode(result["document_id"])
            job = self.registry.require(ref.job_id, ref.site_id)
            try:
                current = await self.graph.item(job, ref.drive_id, ref.item_id)
            except ConnectorError as exc:
                if exc.code == "unavailable":
                    continue
                raise
            self.guard(job)
            result.update(name=current["name"], source_url=current["webUrl"], etag=current.get("eTag"),
                          modified=current.get("lastModifiedDateTime"))
            verified.append(result)
        for result in verified:
            ref = DocumentRef.decode(result["document_id"])
            self.registry.require(ref.job_id, ref.site_id)
        return {"results": verified, "coverage": {
            "complete_within_accessible_supported_content": complete,
            "limit_reasons": sorted(set(limit_reasons)),
            "method": "Live keyword matching over filenames and folder paths, not file contents or semantic search.",
            "note": "No persistent index. Each search re-enumerates approved accessible libraries. Narrow by job_id when coverage is limited.",
        }}

    async def read_approved_document(self, document_id: str) -> dict[str, Any]:
        self.principal.require_active()
        ref = DocumentRef.decode(document_id)
        job = self.registry.require(ref.job_id, ref.site_id)
        before = await self.graph.item(job, ref.drive_id, ref.item_id)
        self.guard(job)
        if before.get("file") is None or not supported(before.get("name", "")):
            raise ConnectorError("unsupported_format")
        if not before.get("eTag"):
            raise ConnectorError("upstream_unavailable")
        data = await self.graph.content(job, ref.drive_id, ref.item_id)
        self.guard(job)
        parse_error = None
        extracted = None
        try:
            extracted = await extract_document(data, before["name"], self.settings)
        except ConnectorError as exc:
            parse_error = exc
        finally:
            del data
        after = await self.graph.item(job, ref.drive_id, ref.item_id)
        self.guard(job)
        if after.get("eTag") != before["eTag"]:
            raise ConnectorError("changed_during_read")
        if parse_error:
            raise parse_error
        return {"document_id": document_id, "job_id": job.job_id, "name": after["name"],
                "source_url": after["webUrl"], "etag": after["eTag"],
                "modified": after.get("lastModifiedDateTime"), **(extracted or {})}
