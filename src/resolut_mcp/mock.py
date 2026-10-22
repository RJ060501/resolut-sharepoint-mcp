"""Fabricated SharePoint behavior for LOCAL testing, never a live auth fallback."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .config import Settings
from .errors import ConnectorError
from .graph import GraphSession
from .models import Principal
from .registry import Job, Registry

MOCK_TENANT = "99999999-9999-4999-8999-999999999999"
USERS = {"alice": "11111111-1111-4111-8111-111111111111", "bob": "22222222-2222-4222-8222-222222222222"}


def mock_principal(user: str = "alice", assertion: str = "synthetic-in-process") -> Principal:
    return Principal(MOCK_TENANT, USERS[user], "mock-client", assertion, int(time.time())+3600)


class MockGraph(GraphSession):
    def __init__(self, settings: Settings, registry: Registry, principal: Principal,
                 dataset: dict[str, Any] | None = None) -> None:
        self.settings = settings
        self.registry = registry
        self.principal = principal
        self.data = dataset if dataset is not None else json.loads((settings.fixtures_path / "catalog.json").read_text())
        self.calls: list[tuple[str, str]] = []
        self._drives = {}

    def _user(self) -> str:
        return next((name for name, oid in USERS.items() if oid == self.principal.object_id), "unknown")

    def human_can_open(self, job_id: str) -> bool:
        return self._user() in self.data["sites"].get(job_id, {}).get("users", [])

    def _site_allowed(self, job: Job) -> None:
        self.guard(job)
        self.calls.append(("site", job.job_id))
        if not self.human_can_open(job.job_id):
            raise ConnectorError("unavailable")

    async def site(self, job: Job) -> dict[str, Any]:
        self._site_allowed(job)
        return {"id": job.site_id, "webUrl": job.site_url, "displayName": job.display_name}

    async def drives(self, job: Job) -> list[dict[str, Any]]:
        self._site_allowed(job)
        return [{"id": "drive-"+job.job_id, "name": "Documents", "driveType": "documentLibrary", "webUrl": job.site_url+"/Documents"}]

    def _metadata(self, job: Job, row: dict[str, Any]) -> dict[str, Any]:
        actual_site = row.get("site_id", job.site_id)
        host, collection, web = actual_site.split(",")
        path = row.get("path", row["name"])
        result = {
            "id": row["id"], "name": row["name"], "size": row.get("size", 100),
            "eTag": row.get("etag", '"synthetic-v1"'), "lastModifiedDateTime": "2026-10-20T12:00:00Z",
            "parentReference": {"driveId": "drive-"+job.job_id, "siteId": actual_site},
            "sharepointIds": {"siteId": collection, "webId": web},
            "webUrl": row.get("web_url", job.site_url+"/Documents/"+quote(path)),
        }
        if row.get("folder"):
            result["folder"] = {}
        else:
            result["file"] = {"mimeType": "application/octet-stream"}
        if row.get("remote"):
            result["remoteItem"] = {"id": "remote-excluded"}
        return result

    async def children(self, job: Job, drive_id: str, folder_id: str | None = None):
        self._site_allowed(job)
        if drive_id != "drive-"+job.job_id:
            raise ConnectorError("unavailable")
        for row in self.data["documents"]:
            if row["job_id"] == job.job_id and row.get("parent") == folder_id and self._user() in row["users"]:
                self.guard(job)
                yield self._metadata(job, row)

    async def item(self, job: Job, drive_id: str, item_id: str) -> dict[str, Any]:
        self._site_allowed(job)
        self.calls.append(("item", item_id))
        if drive_id != "drive-"+job.job_id:
            raise ConnectorError("unavailable")
        row = next((r for r in self.data["documents"] if r["id"] == item_id and r["job_id"] == job.job_id), None)
        if row is None or self._user() not in row["users"]:
            raise ConnectorError("unavailable")
        result = self._metadata(job, row)
        self.validate_item(job, drive_id, result)
        return result

    async def content(self, job: Job, drive_id: str, item_id: str) -> bytes:
        await self.item(job, drive_id, item_id)
        self.calls.append(("content", item_id))
        row = next(r for r in self.data["documents"] if r["id"] == item_id and r["job_id"] == job.job_id)
        if row.get("folder"):
            raise ConnectorError("unsupported_format")
        path = (self.settings.fixtures_path / row["fixture"]).resolve()
        if not path.is_relative_to(self.settings.fixtures_path.resolve()):
            raise ConnectorError("unavailable")
        data = path.read_bytes()
        if len(data) > self.settings.max_file_bytes:
            raise ConnectorError("file_too_large")
        self.guard(job)
        return data
