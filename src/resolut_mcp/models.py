from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit
from uuid import UUID

from .errors import ConnectorError

_SAFE_ID = re.compile(r"^[A-Za-z0-9_!.-]{1,256}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def identifier(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise ConnectorError("invalid_request")
    return value


def job_identifier(value: str) -> str:
    if not isinstance(value, str) or not _JOB_ID.fullmatch(value):
        raise ConnectorError("invalid_request")
    return value


def normalized_site_id(value: str, host: str | None = None) -> str:
    try:
        hostname, collection, web = value.split(",")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+", hostname.lower()):
            raise ValueError()
        if host and hostname.lower() != host.lower():
            raise ValueError()
        return f"{hostname.lower()},{UUID(collection)},{UUID(web)}"
    except (AttributeError, TypeError, ValueError):
        raise ConnectorError("unavailable") from None


def safe_https_url(value: str, host: str) -> str:
    try:
        u = urlsplit(value)
        if u.scheme != "https" or u.hostname != host or u.port not in {None, 443}:
            raise ValueError()
        if u.username or u.password or u.fragment or "\\" in value:
            raise ValueError()
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ConnectorError("unavailable") from None


def path_under_site(url: str, site_url: str, host: str) -> bool:
    try:
        safe_https_url(url, host)
        path = unquote(urlsplit(url).path).rstrip("/").casefold()
        base = unquote(urlsplit(site_url).path).rstrip("/").casefold()
        if any(p in {".", ".."} for p in path.split("/")) or "\\" in path:
            return False
        return path == base or path.startswith(base + "/")
    except ConnectorError:
        return False


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    object_id: str
    client_id: str
    assertion: str = field(repr=False)
    expires_at: int = 0

    def require_active(self) -> None:
        if self.expires_at <= time.time():
            raise ConnectorError("authentication_required")


@dataclass(frozen=True)
class DocumentRef:
    job_id: str
    site_id: str
    drive_id: str
    item_id: str

    def encode(self) -> str:
        payload = json.dumps([self.job_id, self.site_id, self.drive_id, self.item_id], separators=(",", ":"))
        return "v1." + base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> DocumentRef:
        # An identifier is NOT a capability or a secret. Every use reauthorizes it.
        try:
            if not isinstance(value, str) or not value.startswith("v1.") or len(value) > 1800:
                raise ValueError()
            encoded = value[3:]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
                raise ValueError()
            items = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if not isinstance(items, list) or len(items) != 4 or not all(isinstance(x, str) for x in items):
                raise ValueError()
            job, site, drive, item = items
            return cls(job_identifier(job), normalized_site_id(site), identifier(drive), identifier(item))
        except (ValueError, TypeError, UnicodeError, ConnectorError):
            # Do not distinguish an excluded identifier from a nonexistent one.
            raise ConnectorError("unavailable") from None
