"""Bounded, read-only Graph transport. No general-purpose request tool is exposed."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit
from uuid import UUID

import httpx

from .config import Settings
from .errors import ConnectorError
from .models import Principal, identifier, normalized_site_id, path_under_site, safe_https_url
from .registry import Job, Registry

GRAPH = "https://graph.microsoft.com/v1.0"
ITEM_FIELDS = "id,name,size,file,folder,package,remoteItem,deleted,parentReference,sharepointIds,webUrl,eTag,lastModifiedDateTime"


def _segment(value: str) -> str:
    return quote(value, safe="")


def next_url(url: str, original_path: str) -> str:
    """An upstream nextLink may only paginate the collection already authorized."""
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname != "graph.microsoft.com" or u.port not in {None, 443}
            or u.username or u.password or u.fragment or "\\" in url
            or unquote(u.path) != unquote("/v1.0" + original_path)):
        raise ConnectorError("upstream_unavailable")
    return url


def retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = parsedate_to_datetime(value).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                delay = 2 ** attempt
        if delay > 10:
            # Do not hammer Graph sooner than a long Retry-After permits.
            raise ConnectorError("throttled")
        return max(0, delay)
    return min(2 ** attempt, 8)


class GraphSession:
    """One employee, one tool call. Metadata and tokens never cross request owners."""
    def __init__(self, settings: Settings, registry: Registry, principal: Principal,
                 token: str, client: httpx.AsyncClient,
                 sleep: Callable[..., Any] = asyncio.sleep) -> None:
        self.settings = settings
        self.registry = registry
        self.principal = principal
        self._token = token
        self.client = client
        self.sleep = sleep
        self._drives: dict[str, set[str]] = {}

    def guard(self, job: Job) -> Job:
        self.principal.require_active()
        return self.registry.require(job.job_id, job.site_id)

    async def _bytes(self, job: Job, url: str, *, limit: int,
                     bearer: bool = True, allow_download_redirect: bool = False) -> tuple[bytes, str | None]:
        for attempt in range(3):
            self.guard(job)
            headers = {"Accept": "application/json" if not allow_download_redirect else "*/*"}
            if bearer:
                headers["Authorization"] = "Bearer " + self._token
            try:
                async with self.client.stream("GET", url, headers=headers, follow_redirects=False,
                                               timeout=self.settings.graph_timeout_seconds) as response:
                    status = response.status_code
                    if status in {429, 502, 503, 504}:
                        if attempt == 2:
                            raise ConnectorError("throttled" if status == 429 else "upstream_unavailable")
                        delay = retry_delay(response.headers.get("Retry-After"), attempt)
                        await self.sleep(delay)
                        continue
                    if status in {401, 403, 404, 410}:
                        raise ConnectorError("unavailable")
                    if status in {301, 302, 303, 307, 308}:
                        if not allow_download_redirect:
                            raise ConnectorError("upstream_unavailable")
                        location = response.headers.get("Location")
                        if not location:
                            raise ConnectorError("upstream_unavailable")
                        self.guard(job)
                        return b"", location
                    if status != 200:
                        raise ConnectorError("upstream_unavailable")
                    size = response.headers.get("Content-Length")
                    if size and (not size.isdigit() or int(size) > limit):
                        raise ConnectorError("file_too_large" if allow_download_redirect else "upstream_unavailable")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise ConnectorError("file_too_large" if allow_download_redirect else "upstream_unavailable")
                    self.guard(job)
                    return bytes(body), None
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2:
                    raise ConnectorError("upstream_unavailable") from None
                await self.sleep(2 ** attempt)
            except httpx.HTTPError:
                raise ConnectorError("upstream_unavailable") from None
        raise ConnectorError("upstream_unavailable")

    async def json(self, job: Job, path: str, query: dict[str, str] | None = None,
                   absolute: str | None = None) -> dict[str, Any]:
        url = absolute or str(httpx.URL(GRAPH + path, params=query))
        body, _ = await self._bytes(job, url, limit=4*1024*1024)
        try:
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, TypeError):
            raise ConnectorError("upstream_unavailable") from None

    async def collection(self, job: Job, path: str, fields: str) -> AsyncIterator[dict[str, Any]]:
        url: str | None = None
        visited: set[str] = set()
        for _ in range(self.settings.max_pages):
            data = await self.json(job, path, {"$select": fields, "$top": str(self.settings.page_size)}, url)
            values = data.get("value")
            if not isinstance(values, list) or not all(isinstance(x, dict) for x in values):
                raise ConnectorError("upstream_unavailable")
            for item in values:
                self.guard(job)
                yield item
            link = data.get("@odata.nextLink")
            if not link:
                return
            if not isinstance(link, str) or link in visited:
                raise ConnectorError("upstream_unavailable")
            visited.add(link)
            url = next_url(link, path)
        raise ConnectorError("deadline")

    async def site(self, job: Job) -> dict[str, Any]:
        site = await self.json(job, f"/sites/{_segment(job.site_id)}", {"$select": "id,displayName,webUrl"})
        if normalized_site_id(site.get("id", ""), self.settings.sharepoint_host) != job.site_id:
            raise ConnectorError("unavailable")
        url = safe_https_url(site.get("webUrl", ""), self.settings.sharepoint_host).rstrip("/")
        if url.casefold() != job.site_url.casefold():
            # A renamed/moved site needs an administrator to update its registry URL.
            raise ConnectorError("unavailable")
        return site

    async def drives(self, job: Job) -> list[dict[str, Any]]:
        await self.site(job)
        result = []
        path = f"/sites/{_segment(job.site_id)}/drives"
        async for drive in self.collection(job, path, "id,name,webUrl,driveType"):
            if len(result) >= 100:
                raise ConnectorError("deadline")
            if (drive.get("driveType") != "documentLibrary"
                    or not path_under_site(drive.get("webUrl", ""), job.site_url, self.settings.sharepoint_host)):
                continue
            identifier(drive.get("id", ""))
            result.append(drive)
        self._drives[job.site_id] = {d["id"] for d in result}
        return result

    async def _require_drive(self, job: Job, drive_id: str) -> None:
        identifier(drive_id)
        self.guard(job)
        if job.site_id not in self._drives:
            await self.drives(job)
        if drive_id not in self._drives[job.site_id]:
            raise ConnectorError("unavailable")

    async def children(self, job: Job, drive_id: str, folder_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        await self._require_drive(job, drive_id)
        tail = f"items/{_segment(identifier(folder_id))}" if folder_id else "root"
        path = f"/drives/{_segment(drive_id)}/{tail}/children"
        async for item in self.collection(job, path, ITEM_FIELDS):
            # Shortcut/remote targets are not traversed at all in v1.
            if item.get("remoteItem") is not None or item.get("deleted") is not None:
                continue
            yield item

    def validate_item(self, job: Job, drive_id: str, item: dict[str, Any]) -> None:
        self.guard(job)
        if item.get("remoteItem") is not None or item.get("deleted") is not None or item.get("package") is not None:
            raise ConnectorError("unavailable")
        parent = item.get("parentReference") or {}
        sp = item.get("sharepointIds") or {}
        try:
            hostname, collection_id, web_id = job.site_id.split(",")
            # sharepointIds.siteId is the SITE COLLECTION GUID, not Graph's triple.
            if str(UUID(sp["siteId"])) != collection_id or str(UUID(sp["webId"])) != web_id:
                raise ValueError()
            if self.settings.tenant_id and sp.get("tenantId") and str(UUID(sp["tenantId"])) != self.settings.tenant_id:
                raise ValueError()
            if parent.get("driveId") != drive_id:
                raise ValueError()
            if not path_under_site(item["webUrl"], job.site_url, hostname):
                raise ValueError()
            identifier(item["id"])
        except (ValueError, KeyError, TypeError, ConnectorError):
            raise ConnectorError("unavailable") from None

    async def item(self, job: Job, drive_id: str, item_id: str) -> dict[str, Any]:
        await self._require_drive(job, drive_id)
        path = f"/drives/{_segment(drive_id)}/items/{_segment(identifier(item_id))}"
        item = await self.json(job, path, {"$select": ITEM_FIELDS})
        self.validate_item(job, drive_id, item)
        if item.get("id") != item_id:
            raise ConnectorError("unavailable")
        return item

    async def content(self, job: Job, drive_id: str, item_id: str) -> bytes:
        # Re-read authorization and provenance before requesting /content.
        item = await self.item(job, drive_id, item_id)
        if item.get("file") is None or item.get("folder") is not None:
            raise ConnectorError("unsupported_format")
        if not isinstance(item.get("size"), int) or item["size"] < 0 or item["size"] > self.settings.max_file_bytes:
            raise ConnectorError("file_too_large")
        url = GRAPH + f"/drives/{_segment(drive_id)}/items/{_segment(item_id)}/content"
        body, location = await self._bytes(job, url, limit=self.settings.max_file_bytes, allow_download_redirect=True)
        for _ in range(3):
            if location is None:
                return body
            u = urlsplit(location)
            if u.hostname not in self.settings.download_hosts:
                raise ConnectorError("upstream_unavailable")
            safe_https_url(location, u.hostname)
            # Graph /content returns a preauthenticated URL. NEVER forward the
            # Graph Authorization header to that host or return this URL to Claude.
            body, location = await self._bytes(job, location, limit=self.settings.max_file_bytes,
                                               bearer=False, allow_download_redirect=True)
        raise ConnectorError("upstream_unavailable")
