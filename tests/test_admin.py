import json

import pytest

from resolut_mcp.admin import save_registry
from resolut_mcp.errors import ConnectorError


def test_atomic_block_becomes_visible_without_restart(settings,registry):
    """Verify a persisted block decision is observed immediately by an existing registry."""
    assert registry.require("1001")
    data=json.loads(settings.registry_path.read_text())
    data["jobs"][0]["decision"]="blocked"
    save_registry(settings.registry_path,settings.sharepoint_host,data)
    with pytest.raises(ConnectorError): registry.require("1001")


def test_invalid_replacement_does_not_corrupt_previous_registry(settings,registry):
    """Verify rejected policy updates leave the old registry intact and clean temporary files."""
    data=json.loads(settings.registry_path.read_text()); data["jobs"][0]["site_id"]="invalid"
    before=settings.registry_path.read_bytes()
    with pytest.raises(ConnectorError): save_registry(settings.registry_path,settings.sharepoint_host,data)
    assert settings.registry_path.read_bytes()==before
    assert registry.require("1001")
    assert not list(settings.registry_path.parent.glob(".sites-*.json"))
