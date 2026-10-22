from dataclasses import replace
from urllib.parse import unquote

import httpx
import pytest

from resolut_mcp.errors import ConnectorError
from resolut_mcp.graph import GraphSession, next_url, retry_delay


async def make_item(graph, registry):
    job = registry.require("1001")
    return await graph.item(job, "drive-1001", "hvac-text")


async def test_collection_paginates_without_general_search(settings, registry, principal):
    calls = []
    path = "/sites/approved/drives"
    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx.Response(200, json={"value":[{"id":"one"}],
                "@odata.nextLink":"https://graph.microsoft.com/v1.0/sites/approved/drives?$skiptoken=next"})
        return httpx.Response(200, json={"value":[{"id":"two"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        g = GraphSession(settings, registry, principal, "graph-token", client)
        result = [x async for x in g.collection(registry.require("1001"), path, "id")]
    assert [r["id"] for r in result] == ["one","two"]
    assert all(r.headers["Authorization"] == "Bearer graph-token" for r in calls)


@pytest.mark.parametrize("url", [
    "https://attacker.invalid/v1.0/sites/approved/drives", 
    "https://graph.microsoft.com/v1.0/sites/restricted/drives",
    "http://graph.microsoft.com/v1.0/sites/approved/drives",
    "https://graph.microsoft.com:444/v1.0/sites/approved/drives",
    "https://user@graph.microsoft.com/v1.0/sites/approved/drives",
    "https://graph.microsoft.com/v1.0/sites/approved/drives#fragment",
])
def test_nextlink_cannot_change_resource_or_host(url):
    with pytest.raises(ConnectorError): next_url(url,"/sites/approved/drives")


async def test_malicious_nextlink_never_requested(settings, registry, principal):
    seen = []
    def handler(req):
        seen.append(req)
        return httpx.Response(200,json={"value":[],"@odata.nextLink":"https://attacker.invalid/token"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        with pytest.raises(ConnectorError):
            _ = [x async for x in g.collection(registry.require("1001"),"/sites/test/drives","id")]
    assert len(seen) == 1


async def test_retries_throttle_then_success(settings, registry, principal):
    count = 0; sleeps = []
    def handler(req):
        nonlocal count
        count += 1
        return httpx.Response(429, headers={"Retry-After":"0"}) if count < 3 else httpx.Response(200,json={"ok":True})
    async def sleep(n): sleeps.append(n)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c,sleep=sleep)
        assert (await g.json(registry.require("1001"),"/sites/test"))["ok"]
    assert count == 3 and sleeps == [0,0]


async def test_long_retry_after_fails_without_early_retry(settings,registry,principal):
    calls = []
    def handler(req):
        calls.append(req); return httpx.Response(429,headers={"Retry-After":"120"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        with pytest.raises(ConnectorError) as e: await g.json(registry.require("1001"),"/sites/test")
    assert e.value.code == "throttled" and len(calls) == 1


@pytest.mark.parametrize("status",[401,403,404,410])
async def test_access_failures_are_indistinguishable(settings,registry,principal,status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(status,text="PRIVATE JOB NAME"))) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        with pytest.raises(ConnectorError) as e: await g.json(registry.require("1001"),"/sites/test")
    assert e.value.code == "unavailable" and "PRIVATE" not in str(e.value)


async def test_download_redirect_does_not_receive_graph_bearer(settings,registry,principal,graph):
    item = await make_item(graph,registry); calls = []
    def handler(req):
        calls.append(req)
        if req.url.host == "graph.microsoft.com" and req.url.path.endswith("/content"):
            return httpx.Response(302,headers={"Location":"https://example.sharepoint.com/download?temporary=secret"})
        if req.url.host == "example.sharepoint.com": return httpx.Response(200,content=b"approved bytes")
        return httpx.Response(200,json=item)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        g._drives[registry.require("1001").site_id] = {"drive-1001"}
        assert await g.content(registry.require("1001"),"drive-1001","hvac-text") == b"approved bytes"
    assert calls[-1].url.host == "example.sharepoint.com"
    assert "authorization" not in calls[-1].headers
    assert all(r.headers.get("authorization") == "Bearer graph-token" for r in calls[:-1])


async def test_unknown_download_host_is_never_contacted(settings,registry,principal,graph):
    item = await make_item(graph,registry); calls = []
    def handler(req):
        calls.append(req)
        if req.url.path.endswith("/content"):
            return httpx.Response(302,headers={"Location":"https://attacker.invalid/steal"})
        return httpx.Response(200,json=item)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        g._drives[registry.require("1001").site_id] = {"drive-1001"}
        with pytest.raises(ConnectorError): await g.content(registry.require("1001"),"drive-1001","hvac-text")
    assert all(r.url.host == "graph.microsoft.com" for r in calls)


async def test_download_overflow_is_bounded(settings,registry,principal,graph):
    item = await make_item(graph,registry); item["size"]=10
    def handler(req):
        return httpx.Response(200,content=b"x"*200) if req.url.path.endswith("/content") else httpx.Response(200,json=item)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(replace(settings,max_file_bytes=100),registry,principal,"graph-token",c)
        g._drives[registry.require("1001").site_id] = {"drive-1001"}
        with pytest.raises(ConnectorError) as e: await g.content(registry.require("1001"),"drive-1001","hvac-text")
    assert e.value.code == "file_too_large"


async def test_site_collection_and_web_must_both_match(settings,registry,principal,graph):
    item = await make_item(graph,registry)
    async with httpx.AsyncClient() as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        g.validate_item(registry.require("1001"),"drive-1001",item)
        item["sharepointIds"]["webId"]="ffffffff-ffff-4fff-ffff-ffffffffffff"
        with pytest.raises(ConnectorError): g.validate_item(registry.require("1001"),"drive-1001",item)


async def test_missing_provenance_fails_closed(settings,registry,principal,graph):
    item = await make_item(graph,registry); item.pop("sharepointIds")
    async with httpx.AsyncClient() as c:
        g = GraphSession(settings,registry,principal,"graph-token",c)
        with pytest.raises(ConnectorError): g.validate_item(registry.require("1001"),"drive-1001",item)


async def test_pagination_limit_is_explicit(settings,registry,principal):
    def handler(req): return httpx.Response(200,json={"value":[],"@odata.nextLink":"https://graph.microsoft.com/v1.0/sites/test/drives?$skip=2"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        g = GraphSession(replace(settings,max_pages=1),registry,principal,"graph-token",c)
        with pytest.raises(ConnectorError) as e:
            _ = [x async for x in g.collection(registry.require("1001"),"/sites/test/drives","id")]
    assert e.value.code == "deadline"
