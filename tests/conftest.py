from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from resolut_mcp.config import Settings
from resolut_mcp.mock import MockGraph, mock_principal
from resolut_mcp.registry import Registry
from resolut_mcp.service import Service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    """Build isolated mock-mode settings and copy policy data into pytest's temporary directory."""
    policy = tmp_path / "sites.json"
    policy.write_bytes((ROOT / "config/mock-sites.json").read_bytes())
    return Settings(mode="mock", registry_path=policy, sharepoint_host="example.sharepoint.com",
                    public_mcp_url="http://127.0.0.1:8000/mcp", fixtures_path=ROOT / "fixtures",
                    mock_tokens_path=tmp_path / "mock_tokens.json", download_hosts=("example.sharepoint.com",))


@pytest.fixture
def registry(settings):
    """Create a registry bound to this test's isolated policy file and SharePoint host."""
    return Registry(settings.registry_path, settings.sharepoint_host)


@pytest.fixture
def principal():
    """Provide Alice's synthetic identity for tests that need a default caller."""
    return mock_principal("alice")


@pytest.fixture
def graph(settings, registry, principal):
    """Provide the mock Graph client configured with this test's policy and identity."""
    return MockGraph(settings, registry, principal)


@pytest.fixture
def service(settings, registry, principal, graph):
    """Provide the service layer wired to the common isolated test dependencies."""
    return Service(settings, registry, principal, graph)


def mutate_registry(settings, job_id, **updates):
    """Apply selected field changes to a job entry in the test's persisted registry."""
    data = json.loads(settings.registry_path.read_text())
    next(j for j in data["jobs"] if j["job_id"] == job_id).update(updates)
    settings.registry_path.write_text(json.dumps(data))
