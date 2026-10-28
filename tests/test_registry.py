import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from resolut_mcp.errors import ConnectorError
from resolut_mcp.models import DocumentRef, path_under_site
from conftest import mutate_registry


def test_pending_unknown_expired_and_future_approvals_denied(settings, registry):
    """Deny jobs that are not approved, have expired approval, or claim future approval."""
    for job in ("1002", "1004", "unknown"):
        with pytest.raises(ConnectorError):
            registry.require(job)
    mutate_registry(settings, "1001", expires_at="2020-01-01T00:00:00Z")
    with pytest.raises(ConnectorError):
        registry.require("1001")
    mutate_registry(settings, "1001", expires_at=None,
                    approved_at=(datetime.now(timezone.utc)+timedelta(days=10)).isoformat())
    with pytest.raises(ConnectorError):
        registry.require("1001")


@pytest.mark.parametrize("mutation", [
    {"site_url": "https://evil.example/sites/job1001"},
    {"approved_by": None}, {"approved_at": "2026-01-01T00:00:00"},
    {"decision": "probably-fine"}, {"site_id": "invalid"},
])
def test_malformed_registry_fails_closed(settings, registry, mutation):
    """Reject malformed approval records with a stable policy-unavailable error."""
    mutate_registry(settings, "1001", **mutation)
    with pytest.raises(ConnectorError) as error:
        registry.load()
    assert error.value.code == "policy_unavailable"


def test_missing_registry_does_not_reuse_old_approval(settings, registry):
    """Ensure a previously loaded approval cannot survive deletion of its policy file."""
    assert registry.require("1001")
    settings.registry_path.unlink()
    with pytest.raises(ConnectorError) as error:
        registry.require("1001")
    assert error.value.code == "policy_unavailable"


def test_duplicate_site_collection_jobs_rejected(settings, registry):
    """Reject separate jobs that claim the same SharePoint site collection."""
    one, two = registry.load()[:2]
    host, collection, _ = one.site_id.split(",")
    web = two.site_id.split(",")[2]
    mutate_registry(settings, "1002", site_id=f"{host},{collection},{web}")
    with pytest.raises(ConnectorError):
        registry.load()


def test_reference_round_trip(registry):
    """Confirm an opaque document reference encodes and decodes without changing identity."""
    job = registry.require("1001")
    original = DocumentRef(job.job_id, job.site_id, "drive-x", "item-y")
    assert DocumentRef.decode(original.encode()) == original


@pytest.mark.parametrize("url,allowed", [
    ("https://example.sharepoint.com/sites/job1001/Docs/A.txt", True),
    ("https://example.sharepoint.com/sites/job10010/A.txt", False),
    ("https://example.sharepoint.com/sites/job1001/%2e%2e/job1002/A.txt", False),
    ("http://example.sharepoint.com/sites/job1001/A.txt", False),
    ("https://example.sharepoint.com.evil.example/sites/job1001/A.txt", False),
    ("https://example.sharepoint.com@evil.example/sites/job1001/A.txt", False),
])
def test_site_url_boundary(url, allowed):
    """Check site containment rejects lookalike hosts, traversal, and non-HTTPS URLs."""
    assert path_under_site(url, "https://example.sharepoint.com/sites/job1001", "example.sharepoint.com") is allowed
