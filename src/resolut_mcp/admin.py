"""Local administrator-only registry maintenance. Never registered as MCP tools.

Run as the deployment administrator, not the runtime service account. Microsoft
resource grants are intentionally managed separately by site_permissions.ps1.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .errors import ConnectorError
from .models import job_identifier, normalized_site_id, safe_https_url
from .registry import Registry


def save_registry(path: Path, host: str, data: dict) -> None:
    """Validate a temporary replacement and atomically publish it on one filesystem."""
    path = path.resolve()
    if not path.is_file():
        raise ValueError("Create the protected registry from the example before editing it.")
    existing = path.stat()
    fd, temporary = tempfile.mkstemp(prefix=".sites-", suffix=".json", dir=path.parent)
    candidate = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if os.name == "posix":
            os.chmod(candidate, existing.st_mode & 0o777)
            os.chown(candidate, existing.st_uid, existing.st_gid)
        Registry(candidate, host).load()
        os.replace(candidate, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        candidate.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--host", required=True, help="Exact tenant.sharepoint.com hostname")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("validate")
    add = commands.add_parser("add", help="Add a PENDING job; does not grant Microsoft access")
    add.add_argument("--job-id", required=True)
    add.add_argument("--site-id", required=True)
    add.add_argument("--site-url", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--owner", required=True)
    for action in ("approve", "block", "remove"):
        sub = commands.add_parser(action)
        sub.add_argument("--job-id", required=True)
        if action == "approve":
            sub.add_argument("--approver", required=True)
            sub.add_argument("--expires-at", help="Optional timezone-aware ISO timestamp")
            sub.add_argument("--confirm-entire-site-reviewed", action="store_true", required=True)
    args = parser.parse_args()
    try:
        registry = Registry(args.registry, args.host)
        registry.load()
        if args.action == "validate":
            print("Registry is valid. This does not test Microsoft grants or employee access.")
            return
        data = json.loads(args.registry.read_text(encoding="utf-8"))
        jid = job_identifier(args.job_id)
        matches = [r for r in data["jobs"] if r["job_id"] == jid]
        if args.action == "add":
            if matches:
                raise ValueError("Job already exists; do not silently retarget a stable job identifier.")
            data["jobs"].append({"job_id": jid, "site_id": normalized_site_id(args.site_id, args.host),
                                 "site_url": safe_https_url(args.site_url, args.host),
                                 "display_name": args.name, "owner": args.owner,
                                 "decision": "pending", "approved_by": None, "approved_at": None,
                                 "expires_at": None})
        else:
            if len(matches) != 1:
                raise ValueError("Job was not found in this registry.")
            row = matches[0]
            if args.action == "approve":
                row.update(decision="approved", approved_by=args.approver,
                           approved_at=datetime.now(timezone.utc).isoformat(), expires_at=args.expires_at)
            elif args.action == "block":
                row["decision"] = "blocked"
            elif args.action == "remove":
                if row["decision"] != "blocked":
                    raise ValueError("Block the job and revoke its Microsoft grant before removal.")
                data["jobs"].remove(row)
        save_registry(args.registry, args.host, data)
        print("Registry updated atomically. Microsoft site grants were NOT changed.")
        if args.action in {"block", "remove"}:
            print("Revoke the separate Microsoft resource grant; handle prior conversations separately.")
    except (ValueError, OSError, ConnectorError) as exc:
        parser.exit(1, f"Registry operation failed: {exc}\n")


if __name__ == "__main__":
    main()
