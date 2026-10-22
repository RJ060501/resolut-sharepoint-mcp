"""Single-tenant Entra JWT validation and delegated on-behalf-of exchange.

The incoming token is for THIS API, not Graph. Only MSAL exchanges it for a
Graph delegated token. Neither component uses client-credentials/app-only reads.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

import httpx
import jwt
import requests

from .config import Settings
from .errors import ConnectorError
from .models import Principal


class KeySource(Protocol):
    async def key(self, kid: str) -> Any: ...


class EntraKeys:
    def __init__(self, tenant_id: str, client: httpx.AsyncClient) -> None:
        self.url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        self.client = client
        self.keys: dict[str, Any] = {}
        self.updated_at = 0.0
        self.lock = asyncio.Lock()

    async def key(self, kid: str) -> Any:
        now = time.monotonic()
        if kid in self.keys and now - self.updated_at < 300:
            return self.keys[kid]
        async with self.lock:
            now = time.monotonic()
            if kid in self.keys and now - self.updated_at < 300:
                return self.keys[kid]
            if kid not in self.keys and self.updated_at and now - self.updated_at < 30:
                raise ConnectorError("authentication_required")
            try:
                async with self.client.stream("GET", self.url, follow_redirects=False, timeout=8) as response:
                    if response.status_code != 200:
                        raise ValueError()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 512*1024:
                            raise ValueError()
                import json
                entries = json.loads(body)["keys"]
                keys = {}
                for entry in entries:
                    if entry.get("kty") == "RSA" and entry.get("use", "sig") == "sig":
                        keys[entry["kid"]] = jwt.PyJWK.from_dict(entry, algorithm="RS256").key
                if not keys:
                    raise ValueError()
                self.keys = keys
                self.updated_at = now
            except (httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError):
                # No stale-key fallback after the cache's expiry.
                raise ConnectorError("authentication_required") from None
            if kid not in self.keys:
                raise ConnectorError("authentication_required")
            return self.keys[kid]


class EntraValidator:
    def __init__(self, settings: Settings, keys: KeySource) -> None:
        self.settings = settings
        self.keys = keys

    async def verify(self, token: str) -> Principal:
        try:
            if not token or len(token) > 32768:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("jku") or header.get("x5u"):
                raise ValueError()
            kid = header.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 256:
                raise ValueError()
            key = await self.keys.key(kid)
            claims = jwt.decode(
                token, key=key, algorithms=["RS256"], audience=self.settings.api_client_id,
                issuer=self.settings.issuer, leeway=30,
                options={"require": ["exp", "iat", "nbf", "aud", "iss", "tid", "oid", "azp", "scp", "ver"],
                         "strict_aud": True},
            )
            if claims["ver"] != "2.0" or claims["tid"] != self.settings.tenant_id:
                raise ValueError()
            if claims["azp"] != self.settings.claude_client_id or claims.get("idtyp") == "app":
                raise ValueError()
            if not isinstance(claims["scp"], str) or "access_as_user" not in claims["scp"].split():
                raise ValueError()
            oid = str(UUID(claims["oid"]))
            principal = Principal(self.settings.tenant_id, oid, claims["azp"], token, int(claims["exp"]))
            principal.require_active()
            return principal
        except (jwt.PyJWTError, ConnectorError, ValueError, TypeError, KeyError):
            raise ConnectorError("authentication_required") from None


class _TimeoutSession(requests.Session):
    """MSAL's supported requests-compatible HTTP client with bounded I/O."""
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (5, 15)
        return super().request(method, url, **kwargs)


class OboTokenProvider:
    def __init__(self, settings: Settings, app_factory: Callable[..., Any] | None = None) -> None:
        self.settings = settings
        if app_factory is None:
            from msal import ConfidentialClientApplication
            app_factory = ConfidentialClientApplication
        self.factory = app_factory
        self.lock = threading.Lock()
        self.app: Any = None
        self.session = _TimeoutSession()
        self.session.trust_env = False

    def _exchange(self, principal: Principal) -> str:
        principal.require_active()
        try:
            with self.lock:
                if self.app is None:
                    credential: Any = self.settings.api_client_secret
                    if self.settings.certificate_path:
                        credential = {
                            "private_key": self.settings.certificate_path.read_text(),
                            "thumbprint": self.settings.certificate_thumbprint,
                        }
                    self.app = self.factory(
                        self.settings.api_client_id, client_credential=credential,
                        authority=self.settings.authority, http_client=self.session,
                        enable_pii_log=False,
                    )
                result = self.app.acquire_token_on_behalf_of(
                    user_assertion=principal.assertion,
                    scopes=["https://graph.microsoft.com/.default"],
                )
            principal.require_active()
            if "access_token" not in result:
                # No raw error_description or claims challenge is passed to the model.
                raise ConnectorError("authentication_required")
            scopes = {x.removeprefix("https://graph.microsoft.com/") for x in str(result.get("scope", "")).split()}
            allowed = {"Sites.Selected", "openid", "profile", "email"}
            if "Sites.Selected" not in scopes or not scopes.issubset(allowed):
                raise ConnectorError("authorization_configuration")
            return str(result["access_token"])
        except ConnectorError:
            raise
        except Exception:
            # A failed MSAL exchange cannot become anonymous or app-only access.
            raise ConnectorError("authentication_required") from None

    async def token(self, principal: Principal) -> str:
        return await asyncio.to_thread(self._exchange, principal)

    def close(self) -> None:
        self.session.close()
