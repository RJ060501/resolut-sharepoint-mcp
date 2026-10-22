from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from dotenv import load_dotenv


def _number(name: str, default: int, low: int, high: int) -> int:
    result = int(os.getenv(name, str(default)))
    if not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")
    return result


@dataclass(frozen=True)
class Settings:
    mode: str
    registry_path: Path
    sharepoint_host: str
    public_mcp_url: str
    tenant_id: str = ""
    api_client_id: str = ""
    claude_client_id: str = ""
    api_client_secret: str = field(default="", repr=False)
    certificate_path: Path | None = None
    certificate_thumbprint: str = ""
    mock_tokens_path: Path = Path(".local/mock_tokens.json")
    fixtures_path: Path = Path("fixtures")
    download_hosts: tuple[str, ...] = ()
    max_file_bytes: int = 10 * 1024 * 1024
    max_text_chars: int = 60000
    max_pdf_pages: int = 100
    max_scan_items: int = 2000
    max_search_results: int = 25
    max_sites: int = 10
    max_pages: int = 100
    request_seconds: int = 150
    graph_timeout_seconds: int = 20
    extraction_seconds: int = 20
    max_concurrent_tools: int = 4
    page_size: int = 100
    mode_label: str = "pilot"

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def oauth_scope(self) -> str:
        # This URL must also be an Entra Application ID URI. Do not replace it
        # with api://...: Claude sends the MCP endpoint as its resource indicator.
        return self.public_mcp_url + "/access_as_user"

    @classmethod
    def from_env(cls, env_file: str | None = None) -> Settings:
        load_dotenv(env_file or ".env", override=False)
        mode = os.getenv("MODE", "").lower()
        if mode not in {"live", "mock"}:
            raise ValueError("Set MODE explicitly to live or mock.")
        host = os.getenv("SHAREPOINT_HOST", "example.sharepoint.com" if mode == "mock" else "").lower()
        public = os.getenv("PUBLIC_MCP_URL", "http://127.0.0.1:8000/mcp" if mode == "mock" else "").rstrip("/")
        u = urlsplit(public)
        if u.path != "/mcp" or u.query or u.fragment or u.username or u.password:
            raise ValueError("PUBLIC_MCP_URL must be an origin followed by exactly /mcp.")
        if mode == "mock":
            if u.scheme != "http" or u.hostname not in {"127.0.0.1", "localhost"}:
                raise ValueError("Mock mode is loopback-only and cannot use a public MCP URL.")
        elif u.scheme != "https" or not u.hostname or u.port not in {None, 443}:
            raise ValueError("Live PUBLIC_MCP_URL requires HTTPS on port 443.")
        if not host.endswith(".sharepoint.com") or "/" in host or ":" in host:
            raise ValueError("SHAREPOINT_HOST must be your exact commercial SharePoint hostname.")
        tenant = os.getenv("TENANT_ID", "")
        api = os.getenv("API_CLIENT_ID", "")
        client = os.getenv("CLAUDE_CLIENT_ID", "")
        secret = os.getenv("API_CLIENT_SECRET", "")
        cert = os.getenv("API_CERTIFICATE_PATH", "")
        thumb = os.getenv("API_CERTIFICATE_THUMBPRINT", "")
        if mode == "live":
            tenant, api, client = (str(UUID(x)) for x in (tenant, api, client))
            if bool(secret) == bool(cert):
                raise ValueError("Configure exactly one API client secret or certificate private-key file.")
            if cert and not thumb:
                raise ValueError("Certificate authentication requires its registered thumbprint.")
            if api == client:
                raise ValueError("Use distinct API and Claude OAuth client registrations.")
        elif any((tenant, api, client, secret, cert)):
            raise ValueError("Do not put live identity credentials in mock mode.")
        download_hosts = tuple(x.strip().lower() for x in os.getenv("DOWNLOAD_HOSTS", host).split(",") if x.strip())
        for h in download_hosts:
            if not h.endswith(".sharepoint.com") or any(c in h for c in "/:@* "):
                raise ValueError("DOWNLOAD_HOSTS must list exact approved SharePoint HTTPS hostnames, not wildcards.")
        return cls(
            mode=mode,
            registry_path=Path(os.getenv("REGISTRY_PATH", "config/mock-sites.json" if mode == "mock" else "/etc/resolut-mcp/sites.json")).resolve(),
            sharepoint_host=host, public_mcp_url=public, tenant_id=tenant,
            api_client_id=api, claude_client_id=client, api_client_secret=secret,
            certificate_path=Path(cert).resolve() if cert else None, certificate_thumbprint=thumb,
            mock_tokens_path=Path(os.getenv("MOCK_TOKENS_PATH", ".local/mock_tokens.json")).resolve(),
            fixtures_path=Path(os.getenv("FIXTURES_PATH", "fixtures")).resolve(), download_hosts=download_hosts,
            max_file_bytes=_number("MAX_FILE_BYTES", 10*1024*1024, 1024, 25*1024*1024),
            max_text_chars=_number("MAX_TEXT_CHARS", 60000, 1000, 90000),
            max_pdf_pages=_number("MAX_PDF_PAGES", 100, 1, 500),
            max_scan_items=_number("MAX_SCAN_ITEMS", 2000, 1, 20000),
            max_search_results=_number("MAX_SEARCH_RESULTS", 25, 1, 100),
            max_sites=_number("MAX_SITES_PER_CALL", 10, 1, 100),
            max_pages=_number("MAX_PAGES_PER_COLLECTION", 100, 1, 1000),
            request_seconds=_number("REQUEST_SECONDS", 150, 10, 210),
            graph_timeout_seconds=_number("GRAPH_TIMEOUT_SECONDS", 20, 2, 30),
            extraction_seconds=_number("EXTRACTION_SECONDS", 20, 2, 60),
            max_concurrent_tools=_number("MAX_CONCURRENT_TOOLS", 4, 1, 16),
            page_size=_number("GRAPH_PAGE_SIZE", 100, 1, 200),
        )
