"""Real official-SDK ASGI tests. Missing SDK is an explicit skip, never a fake server.

Set REQUIRE_SDK_TESTS=1 for CI/release: an absent dependency then fails the suite.
These tests use local synthetic identities; they do not prove Entra/Claude login.
"""
import importlib.util
import json
import os
import secrets
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.sdk


@pytest.fixture
def client(settings):
    """Create an authenticated SDK-backed ASGI client or explicitly skip unavailable SDK tests."""
    if importlib.util.find_spec("mcp") is None:
        if os.getenv("REQUIRE_SDK_TESTS") == "1":
            pytest.fail("Required official MCP SDK is not installed; release is blocked.")
        pytest.skip("Official mcp package unavailable in this offline build environment")
    from starlette.testclient import TestClient
    from resolut_mcp.app import create_app
    tokens={"alice":secrets.token_urlsafe(32),"bob":secrets.token_urlsafe(32)}
    settings.mock_tokens_path.write_text(json.dumps(tokens))
    with TestClient(create_app(settings),base_url="http://127.0.0.1:8000") as c:
        yield c,tokens


def rpc(client,user,method,params=None,ident=1):
    """Send one JSON-RPC request to the MCP endpoint using the selected synthetic user."""
    c,tokens=client
    return c.post("/mcp",headers={"Authorization":"Bearer "+tokens[user],
        "Accept":"application/json, text/event-stream", "MCP-Protocol-Version":"2025-11-25"},
        json={"jsonrpc":"2.0","id":ident,"method":method,"params":params or {}})


def structured(response):
    """Assert a successful tool response and normalize its structured or text payload."""
    assert response.status_code == 200, response.text
    result=response.json()["result"]
    assert not result.get("isError"),result
    if "structuredContent" in result: return result["structuredContent"]
    return json.loads(next(c["text"] for c in result["content"] if c["type"]=="text"))


def test_sdk_requires_auth_and_advertises_resource(client):
    """Require bearer authentication and advertise where clients can obtain resource metadata."""
    c,_=client
    response=c.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert response.status_code==401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_sdk_rejects_invalid_bearer(client):
    """Reject requests carrying a malformed or invalid bearer credential."""
    c,_=client
    assert c.post("/mcp",headers={"Authorization":"Bearer wrong"},json={}).status_code==401


def test_sdk_protected_resource_metadata(client,settings):
    """Expose the configured MCP resource URL and supported OAuth scope in metadata."""
    c,_=client
    r=c.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code==200
    assert r.json()["resource"]==settings.public_mcp_url
    assert settings.oauth_scope in r.json()["scopes_supported"]


def test_sdk_initialization_and_tools(client):
    """Verify SDK initialization and the names and read-only annotations of exposed tools."""
    r=rpc(client,"alice","initialize",{"protocolVersion":"2025-11-25","capabilities":{},
        "clientInfo":{"name":"local-acceptance","version":"0.1"}})
    assert r.status_code==200 and "serverInfo" in r.json()["result"]
    result=rpc(client,"alice","tools/list").json()["result"]
    assert {t["name"] for t in result["tools"]}=={
        "list_approved_jobs","search_approved_documents","read_approved_document"}
    assert all(t["annotations"]["readOnlyHint"] for t in result["tools"])


def test_sdk_lists_different_jobs_for_different_users(client):
    """Ensure each caller sees only the approved jobs available to their identity."""
    a=structured(rpc(client,"alice","tools/call",{"name":"list_approved_jobs","arguments":{}}))
    b=structured(rpc(client,"bob","tools/call",{"name":"list_approved_jobs","arguments":{}}))
    assert {j["job_id"] for j in a["jobs"]}=={"1001"}
    assert {j["job_id"] for j in b["jobs"]}=={"1001","1003"}


def test_sdk_search_and_read(client):
    """Exercise document search followed by an authorized read through the SDK transport."""
    found=structured(rpc(client,"alice","tools/call",{"name":"search_approved_documents",
        "arguments":{"query":"approved_hvac","job_id":"1001"}}))
    identifier=found["results"][0]["document_id"]
    read=structured(rpc(client,"alice","tools/call",{"name":"read_approved_document",
        "arguments":{"document_id":identifier}}))
    assert "HVAC" in read["text"] and read["content_is_untrusted"]


def test_sdk_excluded_site_is_safe_tool_error(client):
    """Return a generic tool error for excluded content without leaking fixture identifiers."""
    r=rpc(client,"alice","tools/call",{"name":"search_approved_documents",
        "arguments":{"query":"CANARY","job_id":"1002"}})
    result=r.json()["result"]
    assert result["isError"] is True
    assert "NDA-CANARY-ORBIT-724" not in r.text and "excluded_nda" not in r.text


def test_sdk_rejects_untrusted_origin(client):
    """Reject a cross-origin request from an origin not trusted by the MCP application."""
    c,tokens=client
    r=c.post("/mcp",headers={"Authorization":"Bearer "+tokens["alice"],
         "Origin":"https://attacker.invalid","Accept":"application/json, text/event-stream"},
         json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert r.status_code in {400,403}


def test_sdk_health_is_not_live_authorization_proof(client):
    """Distinguish process health and policy readiness from proof of live authorization."""
    c,_=client
    assert c.get("/healthz").json()["mode"]=="mock"
    assert c.get("/readyz").json()["scope"]=="process_and_policy_only"


def test_actual_msal_library_import():
    """Require the real MSAL API for release testing while allowing explicit offline skips."""
    if importlib.util.find_spec("msal") is None:
        if os.getenv("REQUIRE_SDK_TESTS")=="1": pytest.fail("MSAL missing; release is blocked.")
        pytest.skip("MSAL unavailable in offline build; OBO tests inject a fake token client")
    from msal import ConfidentialClientApplication
    assert callable(ConfidentialClientApplication.acquire_token_on_behalf_of)
