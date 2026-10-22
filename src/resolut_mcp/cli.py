from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import secrets
from pathlib import Path

from .config import Settings
from .errors import ConnectorError
from .mock import MockGraph, mock_principal
from .models import DocumentRef
from .registry import Registry
from .service import Service


def configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("resolut.audit").setLevel(logging.INFO)
    for name in ("httpx", "httpcore", "httpx2", "httpcore2", "msal", "mcp", "pypdf"):
        logging.getLogger(name).setLevel(logging.CRITICAL)


async def demo(settings: Settings) -> None:
    if settings.mode != "mock":
        raise ValueError("The demo only runs in mock mode.")
    registry = Registry(settings.registry_path, settings.sharepoint_host)
    principal = mock_principal()
    graph = MockGraph(settings, registry, principal)
    service = Service(settings, registry, principal, graph)
    print("SYNTHETIC POLICY DEMO -- no Microsoft, Claude, or MCP transport calls")
    print("Human Alice can open excluded job 1002:", graph.human_can_open("1002"))
    print(json.dumps(await service.list_approved_jobs(), indent=2))
    search = await service.search_approved_documents("hvac", "1001")
    print(json.dumps(search, indent=2))
    if search["results"]:
        print(json.dumps(await service.read_approved_document(search["results"][0]["document_id"]), indent=2))
    excluded = next(j for j in registry.load() if j.job_id == "1002")
    try:
        await service.read_approved_document(DocumentRef("1002", excluded.site_id, "drive-1002", "nda-text").encode())
    except ConnectorError as exc:
        print("Excluded-site connector request:", exc.code)
    else:
        raise RuntimeError("Security demonstration FAILED: excluded site returned data.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolut approved-job SharePoint MCP connector")
    parser.add_argument("--env-file", default=".env")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-mock", help="Generate local synthetic bearer tokens; no company credentials.")
    commands.add_parser("demo", help="Run the synthetic policy/extraction demonstration.")
    commands.add_parser("validate-config", help="Validate config and registry, without contacting Microsoft.")
    serve = commands.add_parser("serve", help="Start loopback ASGI server; put HTTPS reverse proxy in front for live mode.")
    serve.add_argument("--require-live", action="store_true")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings.from_env(args.env_file)
    configure_logging()
    if args.command == "init-mock":
        if settings.mode != "mock":
            parser.error("init-mock requires MODE=mock.")
        path = settings.mock_tokens_path
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({name: secrets.token_urlsafe(32) for name in ("alice", "bob")}, handle)
        print(f"Local mock tokens saved to {path}. Keep this file out of Git.")
    elif args.command == "demo":
        asyncio.run(demo(settings))
    elif args.command == "validate-config":
        Registry(settings.registry_path, settings.sharepoint_host).load()
        print(f"Configuration and registry are valid ({settings.mode}). Live authorization is NOT verified.")
    else:
        if args.require_live and settings.mode != "live":
            parser.error("This deployment requires MODE=live; refusing to start mock mode.")
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, access_log=False,
                    proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                    log_level="warning", limit_concurrency=40, timeout_keep_alive=5)


if __name__ == "__main__":
    main()
