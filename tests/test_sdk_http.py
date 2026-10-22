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
    c,tokens=client
    return c.post("/mcp",headers={"Authorization":"Bearer "+tokens[user],
        "Accept":"application/json, text/event-stream", "MCP-Protocol-Version":"2025-11-25"},
        json={"jsonrpc":"2.0","id":ident,"method":method,"params":params or {}})


def structured(response):
    assert response.status_code == 200, response.text
    result=response.json()["result"]
    assert not result.get("isError"),result
    if "structuredContent" in result: return result["structuredContent"]
    return json.loads(next(c["text"] for c in result["content"] if c["type"]=="text"))


def test_sdk_requires_auth_and_advertises_resource(client):
    c,_=client
    response=c.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert response.status_code==401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_sdk_rejects_invalid_bearer(client):
    c,_=client
    assert c.post("/mcp",headers={"Authorization":"Bearer wrong"},json={}).status_code==401


def test_sdk_protected_resource_metadata(client,settings):
    c,_=client
    r=c.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code==200
    assert r.json()["resource"]==settings.public_mcp_url
    assert settings.oauth_scope in r.json()["scopes_supported"]


def test_sdk_initialization_and_tools(client):
    r=rpc(client,"alice","initialize",{"protocolVersion":"2025-11-25","capabilities":{},
        "clientInfo":{"name":"local-acceptance","version":"0.1"}})
    assert r.status_code==200 and "serverInfo" in r.json()["result"]
    result=rpc(client,"alice","tools/list").json()["result"]
    assert {t["name"] for t in result["tools"]}=={
        "list_approved_jobs","search_approved_documents","read_approved_document"}
    assert all(t["annotations"]["readOnlyHint"] for t in result["tools"])


def test_sdk_lists_different_jobs_for_different_users(client):
    a=structured(rpc(client,"alice","tools/call",{"name":"list_approved_jobs","arguments":{}}))
    b=structured(rpc(client,"bob","tools/call",{"name":"list_approved_jobs","arguments":{}}))
    assert {j["job_id"] for j in a["jobs"]}=={"1001"}
    assert {j["job_id"] for j in b["jobs"]}=={"1001","1003"}


def test_sdk_search_and_read(client):
    found=structured(rpc(client,"alice","tools/call",{"name":"search_approved_documents",
        "arguments":{"query":"approved_hvac","job_id":"1001"}}))
    identifier=found["results"][0]["document_id"]
    read=structured(rpc(client,"alice","tools/call",{"name":"read_approved_document",
        "arguments":{"document_id":identifier}}))
    assert "HVAC" in read["text"] and read["content_is_untrusted"]


def test_sdk_excluded_site_is_safe_tool_error(client):
    r=rpc(client,"alice","tools/call",{"name":"search_approved_documents",
        "arguments":{"query":"CANARY","job_id":"1002"}})
    result=r.json()["result"]
    assert result["isError"] is True
    assert "NDA-CANARY-ORBIT-724" not in r.text and "excluded_nda" not in r.text


def test_sdk_rejects_untrusted_origin(client):
    c,tokens=client
    r=c.post("/mcp",headers={"Authorization":"Bearer "+tokens["alice"],
         "Origin":"https://attacker.invalid","Accept":"application/json, text/event-stream"},
         json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert r.status_code in {400,403}


def test_sdk_health_is_not_live_authorization_proof(client):
    c,_=client
    assert c.get("/healthz").json()["mode"]=="mock"
    assert c.get("/readyz").json()["scope"]=="process_and_policy_only"


def test_actual_msal_library_import():
    if importlib.util.find_spec("msal") is None:
        if os.getenv("REQUIRE_SDK_TESTS")=="1": pytest.fail("MSAL missing; release is blocked.")
        pytest.skip("MSAL unavailable in offline build; OBO tests inject a fake token client")
    from msal import ConfidentialClientApplication
    assert callable(ConfidentialClientApplication.acquire_token_on_behalf_of)
