from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import ConnectorError
from .models import job_identifier, normalized_site_id, safe_https_url


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("An explicit timezone is required.")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Job:
    job_id: str
    site_id: str
    site_url: str
    display_name: str
    decision: str
    owner: str
    approved_by: str | None
    approved_at: datetime | None
    expires_at: datetime | None

    def approved(self) -> bool:
        now = datetime.now(timezone.utc)
        return (self.decision == "approved" and bool(self.owner) and bool(self.approved_by)
                and self.approved_at is not None and self.approved_at <= now
                and (self.expires_at is None or now < self.expires_at))


class Registry:
    """Reload on EVERY authorization check. Never retain last-known-good approvals."""

    def __init__(self, path: Path, host: str) -> None:
        self.path = path
        self.host = host

    def load(self) -> list[Job]:
        try:
            raw = self.path.read_bytes()
            if len(raw) > 2*1024*1024:
                raise ValueError()
            data: dict[str, Any] = json.loads(raw)
            if data.get("schema_version") != 1 or not isinstance(data.get("jobs"), list):
                raise ValueError()
            result = []
            seen_jobs: set[str] = set()
            seen_sites: set[str] = set()
            seen_collections: set[str] = set()
            for row in data["jobs"]:
                job_id = job_identifier(row["job_id"])
                site = normalized_site_id(row["site_id"], self.host)
                url = safe_https_url(row["site_url"].rstrip("/"), self.host)
                if urlsplit(url).query or not urlsplit(url).path or urlsplit(url).path == "/":
                    raise ValueError()
                if job_id in seen_jobs or site in seen_sites or site.split(",")[1] in seen_collections or row["decision"] not in {"approved", "blocked", "pending"}:
                    raise ValueError()
                if not isinstance(row.get("display_name"), str) or len(row["display_name"]) > 200:
                    raise ValueError()
                owner = row.get("owner", "")
                approver = row.get("approved_by")
                if not isinstance(owner, str) or (approver is not None and not isinstance(approver, str)):
                    raise ValueError()
                job = Job(job_id, site, url, row["display_name"], row["decision"], owner, approver,
                          _timestamp(row.get("approved_at")), _timestamp(row.get("expires_at")))
                if job.decision == "approved" and (not owner or not approver or not job.approved_at):
                    raise ValueError()
                result.append(job)
                seen_jobs.add(job_id)
                seen_sites.add(site)
                seen_collections.add(site.split(",")[1])
            return result
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ConnectorError):
            raise ConnectorError("policy_unavailable") from None

    def approved_jobs(self) -> list[Job]:
        return [job for job in self.load() if job.approved()]

    def require(self, job_id: str, expected_site: str | None = None) -> Job:
        for job in self.load():
            if job.job_id == job_id and job.approved() and (expected_site is None or job.site_id == expected_site):
                return job
        raise ConnectorError("unavailable")
