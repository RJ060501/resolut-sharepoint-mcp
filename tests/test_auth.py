from dataclasses import replace
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from resolut_mcp.auth import EntraKeys, EntraValidator, OboTokenProvider
from resolut_mcp.errors import ConnectorError
from resolut_mcp.mock import MOCK_TENANT, USERS
from resolut_mcp.models import Principal

API = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
CLIENT = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def live_settings(settings):
    return replace(settings, mode="live", tenant_id=MOCK_TENANT, api_client_id=API,
                   claude_client_id=CLIENT, api_client_secret="synthetic-not-a-secret",
                   public_mcp_url="https://mcp.example.com/mcp")


class LocalKeys:
    def __init__(self, key): self.public = key.public_key()
    async def key(self, kid):
        if kid != "test-key": raise ConnectorError("authentication_required")
        return self.public


def claims(settings):
    now = int(time.time())
    return {"aud": API, "iss": settings.issuer, "tid": MOCK_TENANT,
            "oid": USERS["alice"], "azp": CLIENT, "scp": "access_as_user",
            "ver": "2.0", "iat": now-1, "nbf": now-1, "exp": now+300}


def signed(key, value, **headers):
    return jwt.encode(value, key, algorithm="RS256", headers={"kid": "test-key", **headers})


async def test_valid_signed_access_token(key, live_settings):
    p = await EntraValidator(live_settings, LocalKeys(key)).verify(signed(key, claims(live_settings)))
    assert p.object_id == USERS["alice"]
    assert p.client_id == CLIENT


@pytest.mark.parametrize("update", [
    {"aud": "https://graph.microsoft.com"}, {"aud": [API]},
    {"tid": "ffffffff-ffff-4fff-ffff-ffffffffffff"},
    {"iss": "https://attacker.invalid/issuer"}, {"azp": API},
    {"exp": 1}, {"nbf": int(time.time())+900}, {"ver": "1.0"},
    {"scp": "Sites.Selected"}, {"scp": ["access_as_user"]},
    {"idtyp": "app"}, {"oid": "alice@example.invalid"},
])
async def test_reject_invalid_claims(key, live_settings, update):
    c = {**claims(live_settings), **update}
    with pytest.raises(ConnectorError, match="Sign in"):
        await EntraValidator(live_settings, LocalKeys(key)).verify(signed(key, c))


@pytest.mark.parametrize("remove", ["exp", "azp", "scp", "oid", "aud", "tid"])
async def test_required_claims(key, live_settings, remove):
    c = claims(live_settings); c.pop(remove)
    with pytest.raises(ConnectorError):
        await EntraValidator(live_settings, LocalKeys(key)).verify(signed(key, c))


async def test_reject_untrusted_key_url(key, live_settings):
    with pytest.raises(ConnectorError):
        await EntraValidator(live_settings, LocalKeys(key)).verify(
            signed(key, claims(live_settings), jku="https://attacker.invalid/jwks"))


async def test_reject_hmac_and_tampered_signature(key, live_settings):
    validator = EntraValidator(live_settings, LocalKeys(key))
    wrong = jwt.encode(claims(live_settings), "a"*40, algorithm="HS256", headers={"kid":"test-key"})
    with pytest.raises(ConnectorError): await validator.verify(wrong)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(ConnectorError): await validator.verify(signed(other, claims(live_settings)))


async def test_tenant_jwks_fixed_endpoint_and_bounded_cache(key):
    import json
    entry = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    entry.update(kid="test-key", use="sig")
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"keys":[entry]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = EntraKeys(MOCK_TENANT, client)
        await source.key("test-key"); await source.key("test-key")
        with pytest.raises(ConnectorError): await source.key("attacker-key")
    assert seen == [f"https://login.microsoftonline.com/{MOCK_TENANT}/discovery/v2.0/keys"]


async def test_expired_jwks_does_not_use_stale_keys(key):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        source = EntraKeys(MOCK_TENANT, client)
        source.keys = {"test-key":key.public_key()}; source.updated_at = time.monotonic()-301
        with pytest.raises(ConnectorError): await source.key("test-key")


async def test_obo_uses_assertion_and_returns_different_graph_token(live_settings, principal):
    calls = []
    class App:
        def acquire_token_on_behalf_of(self, **kwargs):
            calls.append(kwargs)
            return {"access_token":"graph-only-token", "scope":"Sites.Selected"}
    provider = OboTokenProvider(live_settings, lambda *a, **kw: App())
    result = await provider.token(principal)
    assert result != principal.assertion
    assert calls == [{"user_assertion":principal.assertion, "scopes":["https://graph.microsoft.com/.default"]}]
    provider.close()


@pytest.mark.parametrize("result,code", [
    ({"access_token":"token", "scope":"Sites.Read.All Sites.Selected"},"authorization_configuration"),
    ({"access_token":"token", "scope":"Files.Read.All"},"authorization_configuration"),
    ({"access_token":"token"},"authorization_configuration"),
    ({"error":"interaction_required", "error_description":"SECRET-NEVER-EXPOSE"},"authentication_required"),
])
async def test_obo_no_broad_scopes_or_failure_fallback(live_settings, principal, result, code):
    class App:
        def acquire_token_on_behalf_of(self, **kwargs): return result
    provider = OboTokenProvider(live_settings, lambda *a, **kw: App())
    with pytest.raises(ConnectorError) as e: await provider.token(principal)
    assert e.value.code == code
    assert "SECRET" not in str(e.value)
    provider.close()


async def test_obo_separates_user_assertions(live_settings, principal):
    seen = []
    class App:
        def acquire_token_on_behalf_of(self, **kwargs):
            seen.append(kwargs["user_assertion"])
            return {"access_token":"for-"+kwargs["user_assertion"], "scope":"Sites.Selected"}
    provider = OboTokenProvider(live_settings, lambda *a, **kw: App())
    other = replace(principal, object_id=USERS["bob"], assertion="bob-assertion")
    assert await provider.token(principal) != await provider.token(other)
    assert seen == [principal.assertion,"bob-assertion"]
    provider.close()
