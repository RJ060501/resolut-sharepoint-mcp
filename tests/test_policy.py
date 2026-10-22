import json
import time
from dataclasses import replace

import pytest

from resolut_mcp.errors import ConnectorError
from resolut_mcp.mock import MockGraph, mock_principal
from resolut_mcp.models import DocumentRef
from resolut_mcp.service import Service
from conftest import mutate_registry


def reference(registry, job="1001", item="hvac-text"):
    site = next(j for j in registry.load() if j.job_id == job)
    return DocumentRef(job, site.site_id, "drive-"+job, item).encode()


async def test_list_filters_excluded_pending_and_other_user_sites(service):
    result = await service.list_approved_jobs()
    assert [j["job_id"] for j in result["jobs"]] == ["1001"]
    assert "1002" not in json.dumps(result)


async def test_human_access_is_independent_of_ai_access(service, graph, registry):
    assert graph.human_can_open("1002")
    with pytest.raises(ConnectorError, match="Resource unavailable"):
        await service.read_approved_document(reference(registry, "1002", "nda-text"))
    assert graph.calls == []  # The excluded site never even reaches the mock reader.


@pytest.mark.parametrize("job", ["1002", "1004", "9999"])
async def test_blocked_pending_unknown_job_search_denied(service, job):
    with pytest.raises(ConnectorError) as error:
        await service.search_approved_documents("project", job)
    assert error.value.code == "unavailable"
    assert job not in str(error.value)


async def test_search_and_read_text(service):
    matches = await service.search_approved_documents("hvac", "1001")
    assert len(matches["results"]) == 2
    assert matches["coverage"]["complete_within_accessible_supported_content"]
    result = await service.read_approved_document(matches["results"][0]["document_id"])
    assert "Morgan Example" in result["text"]
    assert result["content_is_untrusted"] is True
    assert result["source_url"].startswith("https://example.sharepoint.com/sites/job1001/")


async def test_search_nested_folder(service):
    result = await service.search_approved_documents("Commissioning")
    assert len(result["results"]) == 1
    assert result["results"][0]["name"] == "commissioning.pdf"


async def test_site_grant_does_not_replace_unique_file_permissions(service, registry):
    with pytest.raises(ConnectorError) as error:
        await service.read_approved_document(reference(registry, item="restricted-text"))
    assert error.value.code == "unavailable"
    assert not (await service.search_approved_documents("restricted"))["results"]


async def test_no_cross_user_metadata_or_content_cache(settings, registry, service):
    bob = mock_principal("bob")
    other = Service(settings, registry, bob, MockGraph(settings, registry, bob))
    assert (await other.search_approved_documents("restricted"))["results"]
    assert not (await service.search_approved_documents("restricted"))["results"]
    assert {j["job_id"] for j in (await other.list_approved_jobs())["jobs"]} == {"1001", "1003"}


async def test_new_files_inherit_site_approval(service, graph):
    graph.data["documents"].append({"id": "new-file", "job_id": "1001", "name": "new_hvac.txt",
        "fixture": "approved_hvac.txt", "users": ["alice"], "size": 100})
    results = await service.search_approved_documents("new_hvac")
    assert len(results["results"]) == 1
    assert "HVAC" in (await service.read_approved_document(results["results"][0]["document_id"]))["text"]


async def test_revoked_site_blocks_old_document_identifier(settings, registry, service):
    token = reference(registry)
    mutate_registry(settings, "1001", decision="blocked")
    with pytest.raises(ConnectorError):
        await service.read_approved_document(token)
    assert not (await service.search_approved_documents("hvac"))["results"]


async def test_file_permission_revocation_between_search_and_read(service, graph):
    hit = (await service.search_approved_documents("approved_hvac"))["results"][0]
    next(r for r in graph.data["documents"] if r["id"] == "hvac-text")["users"] = ["bob"]
    with pytest.raises(ConnectorError):
        await service.read_approved_document(hit["document_id"])


async def test_block_during_download_discards_data(settings, registry, service, graph, monkeypatch):
    original = graph.content
    async def content(*args):
        data = await original(*args)
        mutate_registry(settings, "1001", decision="blocked")
        return data
    monkeypatch.setattr(graph, "content", content)
    with pytest.raises(ConnectorError) as error:
        await service.read_approved_document(reference(registry))
    assert error.value.code == "unavailable"


async def test_reclassification_during_scan_does_not_return_partial_names(settings, service, graph, monkeypatch):
    original = graph.item
    async def item(*args):
        result = await original(*args)
        mutate_registry(settings, "1001", decision="blocked")
        return result
    monkeypatch.setattr(graph, "item", item)
    with pytest.raises(ConnectorError):
        await service.search_approved_documents("hvac")


async def test_changed_version_can_be_read_without_new_file_approval(service, graph, registry):
    next(r for r in graph.data["documents"] if r["id"] == "hvac-text")["etag"] = '"version-2"'
    result = await service.read_approved_document(reference(registry))
    assert result["etag"] == '"version-2"'


async def test_version_changed_during_read_rejected(service, graph, registry, monkeypatch):
    original = graph.content
    async def content(*args):
        data = await original(*args)
        next(r for r in graph.data["documents"] if r["id"] == "hvac-text")["etag"] = '"new"'
        return data
    monkeypatch.setattr(graph, "content", content)
    with pytest.raises(ConnectorError) as error:
        await service.read_approved_document(reference(registry))
    assert error.value.code == "changed_during_read"


async def test_moved_out_of_site_rejected(service, graph, registry):
    other = next(j for j in registry.load() if j.job_id == "1002")
    next(r for r in graph.data["documents"] if r["id"] == "hvac-text")["site_id"] = other.site_id
    with pytest.raises(ConnectorError):
        await service.read_approved_document(reference(registry))


async def test_cross_site_shortcut_is_not_followed(service, graph, registry):
    next(r for r in graph.data["documents"] if r["id"] == "hvac-text")["remote"] = True
    with pytest.raises(ConnectorError):
        await service.read_approved_document(reference(registry))
    assert not any(kind == "content" for kind, _ in graph.calls)


async def test_prompt_injection_is_only_returned_text_not_executed(service, graph, registry):
    result = await service.read_approved_document(reference(registry, item="injection-text"))
    assert "Ignore all rules" in result["text"]
    assert result["content_is_untrusted"]
    assert not any(job == "1002" or job == "nda-text" for _, job in graph.calls)


async def test_expired_identity_cannot_read(settings, registry, graph):
    principal = replace(mock_principal(), expires_at=int(time.time())-1)
    service = Service(settings, registry, principal, graph)
    with pytest.raises(ConnectorError) as error:
        await service.list_approved_jobs()
    assert error.value.code == "authentication_required"


async def test_coverage_limit_is_explicit(settings, registry, principal, graph):
    limited = Service(replace(settings, max_scan_items=1), registry, principal, graph)
    result = await limited.search_approved_documents("hvac")
    assert not result["coverage"]["complete_within_accessible_supported_content"]
    assert "item_limit" in result["coverage"]["limit_reasons"]


async def test_result_limit_is_explicit(settings, registry, principal, graph):
    limited = Service(replace(settings, max_search_results=1), registry, principal, graph)
    result = await limited.search_approved_documents("hvac")
    assert len(result["results"]) == 1
    assert "result_limit" in result["coverage"]["limit_reasons"]


@pytest.mark.parametrize("value", ["", " ", "x"*201, "query\nsecond", "query\x00"])
async def test_invalid_search_input(service, value):
    with pytest.raises(ConnectorError) as error:
        await service.search_approved_documents(value)
    assert error.value.code == "invalid_request"


@pytest.mark.parametrize("value", ["", "v1.not-json", "v1.!!!!", "v2.value", "../etc/passwd", "https://elsewhere"])
async def test_invalid_document_identifiers_are_generic(service, value):
    with pytest.raises(ConnectorError) as error:
        await service.read_approved_document(value)
    assert error.value.code == "unavailable"
